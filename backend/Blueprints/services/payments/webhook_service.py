from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from extensions import db
from flask import current_app
from mercadopago.webhook import (
    InvalidWebhookSignatureError,
    WebhookSignatureValidator,
)
from models import PaymentWebhookEvent
from sqlalchemy.exc import IntegrityError

from Blueprints.services.payments.mercado_pago_gateway import MercadoPagoGateway
from Blueprints.services.payments.subscription_service import (
    PROVIDER,
    synchronize_invoice_event,
    synchronize_preapproval_event,
)

SUBSCRIPTION_EVENT = "subscription_preapproval"
AUTHORIZED_PAYMENT_EVENT = "subscription_authorized_payment"
SUPPORTED_EVENT_TYPES = {SUBSCRIPTION_EVENT, AUTHORIZED_PAYMENT_EVENT}


class WebhookConfigurationError(RuntimeError):
    pass


class WebhookSignatureError(ValueError):
    pass


class WebhookValidationError(ValueError):
    pass


@dataclass(frozen=True)
class WebhookResult:
    event_type: str
    status: str
    duplicate: bool


def validate_webhook_signature(
    signature_header: str, request_id: str, data_id: str
) -> None:
    secret = str(current_app.config.get("MERCADOPAGO_WEBHOOK_SECRET") or "").strip()
    if not secret:
        raise WebhookConfigurationError("MERCADOPAGO_WEBHOOK_SECRET missing")
    try:
        WebhookSignatureValidator.validate(
            signature_header,
            request_id,
            data_id,
            secret,
            tolerance_seconds=300,
        )
    except (InvalidWebhookSignatureError, ValueError) as exc:
        raise WebhookSignatureError("Assinatura de webhook inválida.") from exc


def process_notification(
    payload: dict[str, Any],
    resource_id: str,
    *,
    request_id: str = "",
    gateway: MercadoPagoGateway | None = None,
) -> WebhookResult:
    event_type = str(payload.get("type") or "").strip()
    if event_type not in SUPPORTED_EVENT_TYPES:
        return WebhookResult(event_type or "unknown", "ignored", False)

    marker = str(payload.get("id") or request_id or "").strip()
    if not marker or not str(resource_id or "").strip():
        raise WebhookValidationError("Notificação sem identificador.")
    event_id = _event_id(event_type, marker)
    existing = PaymentWebhookEvent.query.filter_by(
        provider=PROVIDER, provider_event_id=event_id
    ).first()
    if existing is not None:
        return WebhookResult(event_type, existing.status, True)

    mercado_pago = gateway or MercadoPagoGateway()
    event = PaymentWebhookEvent(
        provider=PROVIDER,
        provider_event_id=event_id,
        event_type=event_type,
        resource_id=resource_id,
        status="processing",
        payload=payload,
    )
    db.session.add(event)

    if event_type == SUBSCRIPTION_EVENT:
        provider_subscription = mercado_pago.get_subscription(resource_id)
        synchronize_preapproval_event(provider_subscription, resource_id)
    else:
        invoice = mercado_pago.get_invoice(resource_id)
        subscription_id = str(invoice.get("preapproval_id") or "").strip()
        if not subscription_id:
            raise WebhookValidationError("Fatura sem assinatura.")
        provider_subscription = mercado_pago.get_subscription(subscription_id)
        synchronize_invoice_event(invoice, provider_subscription, resource_id)

    event.status = "processed"
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        duplicate = PaymentWebhookEvent.query.filter_by(
            provider=PROVIDER, provider_event_id=event_id
        ).first()
        if duplicate is None:
            raise
        return WebhookResult(event_type, duplicate.status, True)
    return WebhookResult(event_type, event.status, False)


def _event_id(event_type: str, marker: str) -> str:
    value = f"{event_type}:{marker}"
    if len(value) <= 120:
        return value
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"{event_type}:{digest}"[:120]
