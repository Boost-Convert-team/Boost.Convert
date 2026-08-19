from __future__ import annotations

import calendar
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from extensions import db
from flask import current_app
from models import Payment, PaymentWebhookEvent, Subscription
from sqlalchemy.exc import IntegrityError

from Blueprints.services.payments.mercado_pago_client import MercadoPagoClient
from Blueprints.services.payments.payment_service import (
    PROVIDER,
    ProviderPaymentValidationError,
    map_subscription_status,
    synchronize_payment_from_provider,
)
from Blueprints.services.payments.plans import get_payment_plan
from Blueprints.services.subscription.subscription_service import (
    as_utc,
    synchronize_user_pro_status,
)

SUBSCRIPTION_EVENT = "subscription_preapproval"
AUTHORIZED_PAYMENT_EVENT = "subscription_authorized_payment"
SUPPORTED_EVENT_TYPES = {SUBSCRIPTION_EVENT, AUTHORIZED_PAYMENT_EVENT}
PAYMENT_EVENT = "payment"


class WebhookValidationError(ValueError):
    pass


class WebhookConfigurationError(RuntimeError):
    pass


class WebhookSignatureError(ValueError):
    pass


@dataclass(frozen=True)
class WebhookResult:
    event_type: str
    status: str
    duplicate: bool


def validate_webhook_signature(
    signature_header: str,
    request_id: str,
    data_id: str,
) -> None:
    secret = str(current_app.config.get("MERCADOPAGO_WEBHOOK_SECRET") or "").strip()
    if not secret:
        raise WebhookConfigurationError("Webhook não configurado.")

    signature = parse_signature_header(signature_header)
    timestamp = signature.get("ts", "")
    received_digest = signature.get("v1", "")
    normalized_data_id = str(data_id or "").strip().lower()
    normalized_request_id = str(request_id or "").strip()
    if not timestamp or not received_digest or not normalized_data_id:
        raise WebhookSignatureError("Assinatura incompleta.")

    manifest = f"id:{normalized_data_id};"
    if normalized_request_id:
        manifest += f"request-id:{normalized_request_id};"
    manifest += f"ts:{timestamp};"
    expected_digest = hmac.new(
        secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_digest, received_digest):
        raise WebhookSignatureError("Assinatura inválida.")


def parse_signature_header(value: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for item in str(value or "").split(","):
        key, separator, part_value = item.strip().partition("=")
        if separator and key and part_value:
            parts[key] = part_value
    return parts


def build_provider_event_id(event_type: str, event_marker: str) -> str:
    event_id = f"{event_type}:{event_marker}"
    if len(event_id) <= 120:
        return event_id
    digest = hashlib.sha256(event_id.encode("utf-8")).hexdigest()
    return f"{event_type}:{digest}"[:120]


def process_payment_notification(
    payload: dict[str, Any],
    resource_id: str,
    *,
    request_id: str = "",
    client: MercadoPagoClient | None = None,
) -> WebhookResult:
    event_type = str(payload.get("type") or "").strip()
    if event_type != PAYMENT_EVENT:
        return WebhookResult(event_type or "unknown", "ignored", False)

    event_marker = str(payload.get("id") or request_id or "").strip()
    normalized_resource_id = str(resource_id or "").strip()
    if not event_marker or not normalized_resource_id:
        raise WebhookValidationError("Notificação de pagamento inválida.")
    provider_event_id = build_provider_event_id(event_type, event_marker)
    existing_event = PaymentWebhookEvent.query.filter_by(
        provider=PROVIDER, provider_event_id=provider_event_id
    ).first()
    if existing_event is not None:
        return WebhookResult(event_type, existing_event.status, True)

    provider_data = (client or MercadoPagoClient()).get_payment(normalized_resource_id)
    provider_payment_id = str(provider_data.get("id") or "").strip()
    external_reference = str(provider_data.get("external_reference") or "").strip()
    payment = (
        Payment.query.filter_by(
            provider=PROVIDER, provider_payment_id=provider_payment_id
        )
        .with_for_update()
        .first()
    )
    if payment is None and external_reference:
        payment = (
            Payment.query.filter_by(
                provider=PROVIDER, external_reference=external_reference
            )
            .with_for_update()
            .first()
        )
    if payment is None or payment.payment_method != "credit_card":
        raise WebhookValidationError("Pagamento local desconhecido.")
    try:
        synchronize_payment_from_provider(
            payment,
            provider_data,
            expected_payment_id=normalized_resource_id,
        )
    except ProviderPaymentValidationError as exc:
        raise WebhookValidationError(str(exc)) from exc

    event = PaymentWebhookEvent(
        provider=PROVIDER,
        provider_event_id=provider_event_id,
        event_type=event_type,
        resource_id=normalized_resource_id,
        status="processed",
        payload=payload,
    )
    db.session.add(event)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        duplicate = PaymentWebhookEvent.query.filter_by(
            provider=PROVIDER, provider_event_id=provider_event_id
        ).first()
        if duplicate is None:
            raise
        return WebhookResult(event_type, duplicate.status, True)
    return WebhookResult(event_type, event.status, False)


def process_subscription_notification(
    payload: dict[str, Any],
    resource_id: str,
    *,
    request_id: str = "",
    client: MercadoPagoClient | None = None,
) -> WebhookResult:
    event_type = str(payload.get("type") or "").strip()
    if event_type not in SUPPORTED_EVENT_TYPES:
        return WebhookResult(event_type or "unknown", "ignored", False)

    event_marker = str(payload.get("id") or request_id or "").strip()
    if not event_marker or not str(resource_id or "").strip():
        raise WebhookValidationError("Notificação de assinatura inválida.")
    provider_event_id = build_provider_event_id(event_type, event_marker)

    existing_event = PaymentWebhookEvent.query.filter_by(
        provider=PROVIDER, provider_event_id=provider_event_id
    ).first()
    if existing_event is not None:
        return WebhookResult(event_type, existing_event.status, True)

    mercado_pago = client or MercadoPagoClient()
    event = PaymentWebhookEvent(
        provider=PROVIDER,
        provider_event_id=provider_event_id,
        event_type=event_type,
        resource_id=str(resource_id),
        status="processing",
        payload=payload,
    )
    db.session.add(event)

    if event_type == SUBSCRIPTION_EVENT:
        provider_subscription = mercado_pago.get_subscription(resource_id)
        subscription = validate_provider_subscription(
            provider_subscription, resource_id
        )
        synchronize_subscription_fields(subscription, provider_subscription)
    else:
        provider_invoice = mercado_pago.get_authorized_payment(resource_id)
        provider_subscription_id = str(
            provider_invoice.get("preapproval_id") or ""
        ).strip()
        if not provider_subscription_id:
            raise WebhookValidationError("Fatura sem assinatura associada.")
        provider_subscription = mercado_pago.get_subscription(provider_subscription_id)
        subscription = validate_provider_subscription(
            provider_subscription, provider_subscription_id
        )
        validate_provider_invoice(provider_invoice, resource_id, subscription)
        synchronize_subscription_fields(subscription, provider_subscription)
        synchronize_authorized_payment(
            subscription, provider_invoice, provider_subscription
        )

    refresh_user_access(subscription)
    event.status = "processed"
    db.session.commit()
    return WebhookResult(event_type, event.status, False)


def validate_provider_subscription(
    provider_subscription: dict[str, Any], expected_subscription_id: str
) -> Subscription:
    provider_id = str(provider_subscription.get("id") or "").strip()
    if provider_id != str(expected_subscription_id):
        raise WebhookValidationError("ID da assinatura não corresponde à notificação.")

    external_reference = str(
        provider_subscription.get("external_reference") or ""
    ).strip()
    subscription = (
        Subscription.query.filter_by(
            provider=PROVIDER, provider_subscription_id=provider_id
        )
        .with_for_update()
        .first()
    )
    if subscription is None and external_reference:
        subscription = (
            Subscription.query.filter_by(
                provider=PROVIDER, external_reference=external_reference
            )
            .with_for_update()
            .first()
        )
    if subscription is None:
        raise WebhookValidationError("Referência de assinatura desconhecida.")
    if external_reference != subscription.external_reference:
        raise WebhookValidationError("Referência da assinatura não corresponde.")
    if (
        subscription.provider_subscription_id
        and subscription.provider_subscription_id != provider_id
    ):
        raise WebhookValidationError("Assinatura associada a outro recurso.")

    provider_plan_id = str(
        provider_subscription.get("preapproval_plan_id") or ""
    ).strip()
    expected_plan_id = str(subscription.provider_plan_id or "").strip()
    if provider_plan_id != expected_plan_id:
        raise WebhookValidationError("Plano da assinatura não corresponde.")

    recurring = provider_subscription.get("auto_recurring")
    if not isinstance(recurring, dict):
        raise WebhookValidationError("Recorrência da assinatura ausente.")
    if recurring.get("frequency") != 1 or recurring.get("frequency_type") != "months":
        raise WebhookValidationError("Recorrência da assinatura não corresponde.")
    validate_amount_and_currency(
        recurring.get("transaction_amount"),
        recurring.get("currency_id"),
        subscription,
    )
    return subscription


def validate_provider_invoice(
    provider_invoice: dict[str, Any],
    expected_invoice_id: str,
    subscription: Subscription,
) -> None:
    if str(provider_invoice.get("id") or "") != str(expected_invoice_id):
        raise WebhookValidationError("ID da fatura não corresponde à notificação.")
    if str(provider_invoice.get("preapproval_id") or "") != str(
        subscription.provider_subscription_id
    ):
        raise WebhookValidationError("Fatura associada a outra assinatura.")
    if str(provider_invoice.get("external_reference") or "") != str(
        subscription.external_reference
    ):
        raise WebhookValidationError("Referência da fatura não corresponde.")
    validate_amount_and_currency(
        provider_invoice.get("transaction_amount"),
        provider_invoice.get("currency_id"),
        subscription,
    )


def validate_amount_and_currency(
    provider_amount: object,
    provider_currency: object,
    subscription: Subscription,
) -> None:
    plan = get_payment_plan(subscription.plan)
    try:
        amount = Decimal(str(provider_amount)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError) as exc:
        raise WebhookValidationError("Valor de assinatura inválido.") from exc
    if not amount.is_finite():
        raise WebhookValidationError("Valor de assinatura inválido.")
    currency = str(provider_currency or "").upper()
    if amount != plan.amount or amount != Decimal(subscription.amount):
        raise WebhookValidationError("Valor não corresponde ao plano.")
    if currency != plan.currency or currency != subscription.currency:
        raise WebhookValidationError("Moeda não corresponde ao plano.")


def synchronize_subscription_fields(
    subscription: Subscription, provider_subscription: dict[str, Any]
) -> None:
    provider_status = str(provider_subscription.get("status") or "").lower()
    subscription.provider_subscription_id = str(provider_subscription["id"])
    subscription.status = map_subscription_status(provider_status)
    subscription.started_at = subscription.started_at or parse_provider_datetime(
        provider_subscription.get("date_created")
    )
    subscription.next_payment_at = parse_provider_datetime(
        provider_subscription.get("next_payment_date")
    )
    subscription.updated_at = utc_now()
    if provider_status in {"canceled", "cancelled"}:
        subscription.canceled_at = subscription.canceled_at or utc_now()


def synchronize_authorized_payment(
    subscription: Subscription,
    provider_invoice: dict[str, Any],
    provider_subscription: dict[str, Any],
) -> None:
    invoice_id = str(provider_invoice["id"])
    payment_data = provider_invoice.get("payment")
    payment_data = payment_data if isinstance(payment_data, dict) else {}
    provider_payment_id = str(payment_data.get("id") or "").strip() or None
    provider_status = str(payment_data.get("status") or "pending").strip().lower()
    payment = Payment.query.filter_by(
        provider=PROVIDER, provider_invoice_id=invoice_id
    ).first()
    if payment is None:
        deterministic_key = str(
            uuid5(NAMESPACE_URL, f"{PROVIDER}:authorized-payment:{invoice_id}")
        )
        payment = Payment(
            user_id=subscription.user_id,
            provider=PROVIDER,
            provider_invoice_id=invoice_id,
            external_reference=subscription.external_reference,
            plan=subscription.plan,
            attempt_id=deterministic_key,
            idempotency_key=deterministic_key,
            payment_method="recurring_subscription",
            amount=subscription.amount,
            currency=subscription.currency,
        )
        db.session.add(payment)

    payment.provider_payment_id = provider_payment_id
    payment.status = map_payment_status(provider_status)
    payment.status_detail = str(payment_data.get("status_detail") or "")[:120]
    payment.payment_created_at = parse_provider_datetime(
        provider_invoice.get("date_created")
    )
    payment.last_provider_sync_at = utc_now()
    subscription.provider_payment_id = provider_payment_id
    subscription.latest_payment_status = provider_status

    if provider_status != "approved" or not provider_payment_id:
        return

    approved_at = (
        parse_provider_datetime(provider_invoice.get("debit_date")) or utc_now()
    )
    period_end = parse_provider_datetime(provider_subscription.get("next_payment_date"))
    if period_end is None or period_end <= approved_at:
        period_end = add_calendar_month(approved_at)
    current_paid_through = as_utc(subscription.paid_through_at)
    subscription.paid_through_at = max(period_end, current_paid_through or period_end)
    subscription.status = "active"
    payment.approved_at = approved_at
    payment.premium_expires_at = period_end


def refresh_user_access(subscription: Subscription) -> None:
    paid_through = as_utc(subscription.paid_through_at)
    active = (
        subscription.status == "active"
        and paid_through is not None
        and paid_through > utc_now()
    )
    synchronize_user_pro_status(subscription.user, active)


def map_payment_status(provider_status: str) -> str:
    return {
        "approved": "approved",
        "rejected": "rejected",
        "canceled": "canceled",
        "cancelled": "canceled",
        "refunded": "canceled",
        "charged_back": "canceled",
        "pending": "pending",
        "in_process": "pending",
        "authorized": "pending",
    }.get(provider_status, "pending")


def add_calendar_month(value: datetime) -> datetime:
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def parse_provider_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
