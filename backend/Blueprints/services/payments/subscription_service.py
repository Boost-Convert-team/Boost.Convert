from __future__ import annotations

import calendar
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from extensions import db
from flask import current_app
from models import Payment, Subscription
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from Blueprints.services.payments.mercado_pago_gateway import (
    MercadoPagoGateway,
    MercadoPagoRequestError,
)
from Blueprints.services.payments.plans import PaymentPlan, get_payment_plan
from Blueprints.services.subscription.subscription_service import (
    as_utc,
    has_active_paid_entitlement,
    synchronize_user_pro_status,
)

PROVIDER = "mercado_pago"
OPEN_STATUSES = {"creating", "pending", "active", "paused"}


class CheckoutValidationError(ValueError):
    pass


class CheckoutConflictError(RuntimeError):
    pass


class ProviderDataError(ValueError):
    pass


class SubscriptionNotFoundError(LookupError):
    pass


def create_pro_subscription(
    usuario: Any,
    request_data: object,
    idempotency_key: object,
    back_url: str,
    *,
    gateway: MercadoPagoGateway | None = None,
) -> Subscription:
    token = _card_token(request_data)
    key = _idempotency_key(idempotency_key)
    plan = get_payment_plan("PRO")
    mercado_pago = gateway or MercadoPagoGateway()

    _lock_user_checkout(usuario.id)
    subscription = Subscription.query.filter_by(
        provider=PROVIDER, checkout_idempotency_key=key
    ).first()
    if subscription is not None:
        _validate_attempt_owner(subscription, usuario.id, plan)
        if subscription.provider_subscription_id:
            return subscription
    else:
        if _find_open_subscription(usuario.id) is not None:
            raise CheckoutConflictError("Já existe uma assinatura PRO em andamento.")
        if has_active_paid_entitlement(usuario.id):
            raise CheckoutConflictError("Seu acesso PRO atual ainda está vigente.")
        subscription = Subscription(
            user_id=usuario.id,
            provider=PROVIDER,
            external_reference=f"boost:subscription:{usuario.id}:{key}",
            checkout_idempotency_key=key,
            plan=plan.code,
            status="creating",
            amount=plan.amount,
            currency=plan.currency,
        )
        db.session.add(subscription)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            subscription = Subscription.query.filter_by(
                provider=PROVIDER, checkout_idempotency_key=key
            ).first()
            if subscription is None:
                raise
            _validate_attempt_owner(subscription, usuario.id, plan)
            if subscription.provider_subscription_id:
                return subscription

    try:
        provider_data = mercado_pago.create_subscription(
            _preapproval_payload(subscription, usuario.email, token, plan, back_url),
            key,
        )
    except MercadoPagoRequestError as exc:
        if exc.status in {400, 402, 422}:
            subscription.status = "error"
            subscription.updated_at = utc_now()
            db.session.commit()
        raise
    _synchronize_subscription(subscription, provider_data, expected_id=None)
    db.session.commit()
    current_app.logger.info(
        "mercadopago_subscription_created user_id=%s subscription_id=%s status=%s",
        usuario.id,
        subscription.provider_subscription_id,
        subscription.status,
    )
    return subscription


def reconcile_subscription(
    subscription: Subscription,
    *,
    gateway: MercadoPagoGateway | None = None,
) -> Subscription:
    if not subscription.provider_subscription_id:
        return subscription
    mercado_pago = gateway or MercadoPagoGateway()
    provider_data = mercado_pago.get_subscription(subscription.provider_subscription_id)
    _validate_provider_subscription(subscription, provider_data)
    _synchronize_subscription(
        subscription,
        provider_data,
        expected_id=subscription.provider_subscription_id,
    )
    for invoice in mercado_pago.search_invoices(subscription.provider_subscription_id):
        _synchronize_invoice(subscription, invoice)
    _refresh_entitlement(subscription)
    db.session.commit()
    return subscription


def cancel_user_subscription(
    usuario: Any, *, gateway: MercadoPagoGateway | None = None
) -> Subscription:
    subscription = (
        Subscription.query.filter(
            Subscription.user_id == usuario.id,
            Subscription.provider == PROVIDER,
            Subscription.provider_subscription_id.isnot(None),
            Subscription.status.in_(OPEN_STATUSES),
        )
        .order_by(Subscription.created_at.desc())
        .first()
    )
    if subscription is None:
        raise SubscriptionNotFoundError("Nenhuma assinatura ativa foi encontrada.")

    mercado_pago = gateway or MercadoPagoGateway()
    provider_data = mercado_pago.cancel_subscription(
        subscription.provider_subscription_id
    )
    _validate_provider_subscription(subscription, provider_data)
    _synchronize_subscription(
        subscription,
        provider_data,
        expected_id=subscription.provider_subscription_id,
    )
    if subscription.status != "canceled":
        raise ProviderDataError("O cancelamento não foi confirmado.")
    _refresh_entitlement(subscription)
    db.session.commit()
    return subscription


def synchronize_preapproval_event(
    provider_data: dict[str, Any], resource_id: str
) -> Subscription:
    subscription = _find_local_subscription(provider_data, resource_id)
    _validate_provider_subscription(subscription, provider_data)
    _synchronize_subscription(subscription, provider_data, expected_id=resource_id)
    _refresh_entitlement(subscription)
    return subscription


def synchronize_invoice_event(
    invoice: dict[str, Any], provider_subscription: dict[str, Any], resource_id: str
) -> Subscription:
    provider_subscription_id = str(invoice.get("preapproval_id") or "").strip()
    subscription = _find_local_subscription(
        provider_subscription, provider_subscription_id
    )
    _validate_provider_subscription(subscription, provider_subscription)
    _validate_invoice(subscription, invoice, resource_id)
    _synchronize_subscription(
        subscription,
        provider_subscription,
        expected_id=provider_subscription_id,
    )
    _synchronize_invoice(subscription, invoice)
    _refresh_entitlement(subscription)
    return subscription


def subscription_response(subscription: Subscription) -> dict[str, object]:
    paid_through = as_utc(subscription.paid_through_at)
    approved = (
        subscription.status == "active"
        and paid_through is not None
        and paid_through > utc_now()
    )
    return {
        "ok": subscription.status not in {"canceled", "error"},
        "attempt_id": subscription.checkout_idempotency_key,
        "subscription_id": subscription.provider_subscription_id,
        "status": subscription.latest_payment_status or subscription.status,
        "approved": approved,
    }


def _preapproval_payload(
    subscription: Subscription,
    payer_email: str,
    card_token: str,
    plan: PaymentPlan,
    back_url: str,
) -> dict[str, object]:
    return {
        "reason": plan.title,
        "external_reference": subscription.external_reference,
        "payer_email": str(payer_email).strip().lower(),
        "card_token_id": card_token,
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": float(plan.amount),
            "currency_id": plan.currency,
        },
        "status": "authorized",
        "back_url": back_url,
    }


def _card_token(request_data: object) -> str:
    if not isinstance(request_data, dict):
        raise CheckoutValidationError("Envie o token do cartão em JSON.")
    token = str(request_data.get("token") or "").strip()
    if not token or len(token) > 2048:
        raise CheckoutValidationError("Token do cartão inválido.")
    return token


def _idempotency_key(value: object) -> str:
    try:
        return str(UUID(str(value or "").strip()))
    except (ValueError, AttributeError) as exc:
        raise CheckoutValidationError(
            "Envie uma chave de idempotência UUID válida."
        ) from exc


def _validate_attempt_owner(
    subscription: Subscription, user_id: int, plan: PaymentPlan
) -> None:
    if subscription.user_id != user_id or subscription.plan != plan.code:
        raise CheckoutValidationError(
            "Chave de idempotência pertence a outra assinatura."
        )


def _find_open_subscription(user_id: int) -> Subscription | None:
    return (
        Subscription.query.filter(
            Subscription.user_id == user_id,
            Subscription.provider == PROVIDER,
            Subscription.status.in_(OPEN_STATUSES),
        )
        .order_by(Subscription.created_at.desc())
        .first()
    )


def _find_local_subscription(
    provider_data: dict[str, Any], expected_id: str
) -> Subscription:
    provider_id = str(provider_data.get("id") or "").strip()
    if not provider_id or provider_id != str(expected_id or "").strip():
        raise ProviderDataError("ID de assinatura divergente.")
    subscription = Subscription.query.filter_by(
        provider=PROVIDER, provider_subscription_id=provider_id
    ).first()
    if subscription is None:
        external_reference = str(provider_data.get("external_reference") or "").strip()
        subscription = Subscription.query.filter_by(
            provider=PROVIDER, external_reference=external_reference
        ).first()
    if subscription is None:
        raise ProviderDataError("Assinatura local não encontrada.")
    return subscription


def _validate_provider_subscription(
    subscription: Subscription, provider_data: dict[str, Any]
) -> None:
    provider_id = str(provider_data.get("id") or "").strip()
    if subscription.provider_subscription_id and (
        provider_id != subscription.provider_subscription_id
    ):
        raise ProviderDataError("ID de assinatura divergente.")
    if str(provider_data.get("external_reference") or "").strip() != str(
        subscription.external_reference or ""
    ):
        raise ProviderDataError("Referência externa divergente.")
    recurring = provider_data.get("auto_recurring")
    if not isinstance(recurring, dict):
        raise ProviderDataError("Recorrência ausente.")
    if recurring.get("frequency") != 1 or recurring.get("frequency_type") != "months":
        raise ProviderDataError("Recorrência divergente.")
    _validate_amount_currency(
        recurring.get("transaction_amount"),
        recurring.get("currency_id"),
        subscription,
    )


def _validate_invoice(
    subscription: Subscription, invoice: dict[str, Any], expected_id: str
) -> None:
    if str(invoice.get("id") or "") != str(expected_id):
        raise ProviderDataError("ID de fatura divergente.")
    if str(invoice.get("preapproval_id") or "") != str(
        subscription.provider_subscription_id
    ):
        raise ProviderDataError("Fatura pertence a outra assinatura.")
    if str(invoice.get("external_reference") or "") != str(
        subscription.external_reference
    ):
        raise ProviderDataError("Referência da fatura divergente.")
    _validate_amount_currency(
        invoice.get("transaction_amount"), invoice.get("currency_id"), subscription
    )


def _validate_amount_currency(
    amount_value: object, currency_value: object, subscription: Subscription
) -> None:
    plan = get_payment_plan(subscription.plan)
    try:
        amount = Decimal(str(amount_value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError) as exc:
        raise ProviderDataError("Valor financeiro inválido.") from exc
    if not amount.is_finite() or amount != plan.amount or amount != subscription.amount:
        raise ProviderDataError("Valor financeiro divergente.")
    currency = str(currency_value or "").upper()
    if currency != plan.currency or currency != subscription.currency:
        raise ProviderDataError("Moeda divergente.")


def _synchronize_subscription(
    subscription: Subscription,
    provider_data: dict[str, Any],
    *,
    expected_id: str | None,
) -> None:
    provider_id = str(provider_data.get("id") or "").strip()
    provider_status = str(provider_data.get("status") or "").strip().lower()
    if not provider_id or (expected_id is not None and provider_id != expected_id):
        raise ProviderDataError("Resposta de assinatura inválida.")
    if not provider_status:
        raise ProviderDataError("Status de assinatura ausente.")
    subscription.provider_subscription_id = provider_id
    subscription.status = _subscription_status(provider_status)
    subscription.started_at = (
        subscription.started_at
        or _provider_datetime(provider_data.get("date_created"))
        or utc_now()
    )
    subscription.next_payment_at = _provider_datetime(
        provider_data.get("next_payment_date")
    )
    subscription.updated_at = utc_now()
    if subscription.status == "canceled":
        subscription.canceled_at = subscription.canceled_at or utc_now()


def _synchronize_invoice(subscription: Subscription, invoice: dict[str, Any]) -> None:
    invoice_id = str(invoice.get("id") or "").strip()
    if not invoice_id:
        raise ProviderDataError("Fatura sem ID.")
    _validate_invoice(subscription, invoice, invoice_id)
    payment_data = invoice.get("payment")
    payment_data = payment_data if isinstance(payment_data, dict) else {}
    payment_status = str(payment_data.get("status") or "pending").strip().lower()
    provider_payment_id = str(payment_data.get("id") or "").strip() or None
    payment = Payment.query.filter_by(
        provider=PROVIDER, provider_invoice_id=invoice_id
    ).first()
    if payment is None:
        attempt_id = str(
            uuid5(NAMESPACE_URL, f"{PROVIDER}:authorized-payment:{invoice_id}")
        )
        payment = Payment(
            user_id=subscription.user_id,
            provider=PROVIDER,
            provider_invoice_id=invoice_id,
            external_reference=subscription.external_reference,
            plan=subscription.plan,
            attempt_id=attempt_id,
            idempotency_key=attempt_id,
            payment_method="recurring_subscription",
            amount=subscription.amount,
            currency=subscription.currency,
        )
        db.session.add(payment)
    payment.provider_payment_id = provider_payment_id
    payment.status = _payment_status(payment_status)
    payment.status_detail = str(payment_data.get("status_detail") or "")[:120]
    payment.payment_created_at = _provider_datetime(invoice.get("date_created"))
    payment.last_provider_sync_at = utc_now()
    subscription.provider_payment_id = provider_payment_id
    subscription.latest_payment_status = payment_status
    if payment_status != "approved" or not provider_payment_id:
        return
    approved_at = _provider_datetime(invoice.get("debit_date")) or utc_now()
    period_end = _provider_datetime(subscription.next_payment_at)
    if period_end is None or period_end <= approved_at:
        period_end = _add_calendar_month(approved_at)
    current_paid_through = as_utc(subscription.paid_through_at)
    subscription.paid_through_at = max(period_end, current_paid_through or period_end)
    if subscription.status not in {"canceled", "paused"}:
        subscription.status = "active"
    payment.approved_at = approved_at
    payment.premium_expires_at = period_end


def _refresh_entitlement(subscription: Subscription) -> None:
    paid_through = as_utc(subscription.paid_through_at)
    active = (
        subscription.status == "active"
        and paid_through is not None
        and paid_through > utc_now()
    )
    synchronize_user_pro_status(subscription.user, active, persist=False)


def _subscription_status(status: str) -> str:
    return {
        "authorized": "active",
        "pending": "pending",
        "paused": "paused",
        "canceled": "canceled",
        "cancelled": "canceled",
    }.get(status, "pending")


def _payment_status(status: str) -> str:
    return {
        "approved": "approved",
        "rejected": "rejected",
        "canceled": "canceled",
        "cancelled": "canceled",
        "refunded": "canceled",
        "charged_back": "canceled",
    }.get(status, "pending")


def _provider_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return as_utc(value)
    normalized = str(value or "").strip()
    if not normalized:
        return None
    try:
        return as_utc(datetime.fromisoformat(normalized.replace("Z", "+00:00")))
    except ValueError:
        return None


def _add_calendar_month(value: datetime) -> datetime:
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _lock_user_checkout(user_id: int) -> None:
    bind = db.session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        db.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": f"subscription-checkout:user:{user_id}"},
        )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
