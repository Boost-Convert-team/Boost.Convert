from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import stripe
from Blueprints.services.subscription.subscription_service import (
    synchronize_user_pro_status,
)
from extensions import db
from flask import current_app
from models import PaymentWebhookEvent, Subscription, Usuario
from sqlalchemy.exc import IntegrityError

PROVIDER = "stripe"
SUPPORTED_EVENTS = {
    "checkout.session.completed",
    "invoice.paid",
    "invoice.payment_failed",
    "customer.subscription.updated",
    "customer.subscription.deleted",
}
ACCESS_STATUSES = {"active", "trialing", "past_due"}


class StripeWebhookError(RuntimeError):
    pass


@dataclass(frozen=True)
class WebhookResult:
    event_type: str
    status: str
    duplicate: bool = False


def construct_event(payload: bytes, signature: str) -> Any:
    secret = str(current_app.config.get("STRIPE_WEBHOOK_SECRET") or "").strip()
    if not secret:
        raise StripeWebhookError("Webhook Stripe não configurado.")
    return stripe.Webhook.construct_event(payload, signature, secret)


def process_event(event: Any) -> WebhookResult:
    event_id = str(_value(event, "id") or "")
    event_type = str(_value(event, "type") or "")
    if not event_id.startswith("evt_") or not event_type:
        raise StripeWebhookError("Evento Stripe inválido.")

    if PaymentWebhookEvent.query.filter_by(
        provider=PROVIDER, provider_event_id=event_id
    ).first():
        return WebhookResult(event_type, "duplicate", True)

    event_record = PaymentWebhookEvent(
        provider=PROVIDER,
        provider_event_id=event_id,
        event_type=event_type,
        resource_id=str(_value(_event_object(event), "id") or "") or None,
        status="processed" if event_type in SUPPORTED_EVENTS else "ignored",
        payload={"livemode": bool(_value(event, "livemode", False))},
    )
    db.session.add(event_record)

    try:
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(_event_object(event))
        elif event_type == "invoice.paid":
            _handle_invoice(_event_object(event), paid=True)
        elif event_type == "invoice.payment_failed":
            _handle_invoice(_event_object(event), paid=False)
        elif event_type == "customer.subscription.updated":
            _sync_subscription(_event_object(event))
        elif event_type == "customer.subscription.deleted":
            _sync_subscription(_event_object(event), deleted=True)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if PaymentWebhookEvent.query.filter_by(
            provider=PROVIDER, provider_event_id=event_id
        ).first():
            return WebhookResult(event_type, "duplicate", True)
        raise

    return WebhookResult(event_type, event_record.status)


def _handle_checkout_completed(session: Any) -> None:
    if _value(session, "mode") != "subscription":
        return
    user = _resolve_user(session)
    customer_id = _id(_value(session, "customer"))
    subscription_id = _id(_value(session, "subscription"))
    if not customer_id or not subscription_id or user.stripe_customer_id != customer_id:
        raise StripeWebhookError("Associação de checkout inválida.")

    subscription = _find_subscription(subscription_id) or Subscription(
        user=user,
        user_id=user.id,
        provider=PROVIDER,
        provider_subscription_id=subscription_id,
        external_reference=str(user.id),
        plan="pro",
        status="pending",
    )
    if subscription.user_id != user.id:
        raise StripeWebhookError("Assinatura associada a outro usuário.")
    subscription.stripe_price_id = _configured_price_id()
    db.session.add(subscription)


def _handle_invoice(invoice: Any, *, paid: bool) -> None:
    subscription_id = _invoice_subscription_id(invoice)
    if not subscription_id:
        return
    subscription_data = _retrieve_subscription(subscription_id)
    subscription = _sync_subscription(subscription_data)
    subscription.provider_payment_id = str(_value(invoice, "id") or "") or None
    subscription.latest_payment_status = "paid" if paid else "failed"
    if paid:
        period_end = _invoice_period_end(invoice) or subscription.current_period_end
        subscription.paid_through_at = period_end
    synchronize_user_pro_status(
        subscription.user, _subscription_grants_access(subscription), persist=False
    )


def _sync_subscription(data: Any, *, deleted: bool = False) -> Subscription:
    subscription_id = str(_value(data, "id") or "")
    if not subscription_id.startswith("sub_"):
        raise StripeWebhookError("ID de assinatura Stripe inválido.")
    user = _resolve_user(data)
    customer_id = _id(_value(data, "customer"))
    if not customer_id or user.stripe_customer_id != customer_id:
        raise StripeWebhookError("Customer Stripe não pertence ao usuário.")

    subscription = _find_subscription(subscription_id) or Subscription(
        user=user,
        user_id=user.id,
        provider=PROVIDER,
        provider_subscription_id=subscription_id,
        external_reference=str(user.id),
        plan="pro",
    )
    if subscription.user_id != user.id:
        raise StripeWebhookError("Assinatura associada a outro usuário.")

    price_id = _subscription_price_id(data)
    is_current_price = price_id == _configured_price_id()
    is_existing_subscription_price = bool(
        subscription.id and subscription.stripe_price_id == price_id
    )
    if not is_current_price and not is_existing_subscription_price:
        raise StripeWebhookError("Price da assinatura não corresponde ao plano PRO.")
    period_end = _subscription_period_end(data)
    status = "canceled" if deleted else str(_value(data, "status") or "pending")
    subscription.status = status
    subscription.stripe_price_id = price_id
    subscription.current_period_end = period_end
    subscription.next_payment_at = period_end
    subscription.cancel_at_period_end = bool(
        _value(data, "cancel_at_period_end", False)
    )
    subscription.canceled_at = (
        _timestamp(_value(data, "canceled_at")) if status == "canceled" else None
    )
    db.session.add(subscription)
    synchronize_user_pro_status(
        user, _subscription_grants_access(subscription), persist=False
    )
    return subscription


def _subscription_grants_access(subscription: Subscription) -> bool:
    return bool(
        subscription.status in ACCESS_STATUSES
        and subscription.paid_through_at
        and _as_utc(subscription.paid_through_at) > datetime.now(timezone.utc)
    )


def _resolve_user(data: Any) -> Usuario:
    metadata = _value(data, "metadata", {}) or {}
    user_id = _value(metadata, "boostconvert_user_id")
    if user_id is None:
        parent = _value(data, "parent", {}) or {}
        details = _value(parent, "subscription_details", {}) or {}
        user_id = _value(_value(details, "metadata", {}) or {}, "boostconvert_user_id")
    try:
        normalized_id = int(str(user_id))
    except (TypeError, ValueError) as exc:
        raise StripeWebhookError("Evento sem usuário interno válido.") from exc
    user = db.session.get(Usuario, normalized_id)
    if user is None:
        raise StripeWebhookError("Usuário do evento não existe.")
    return user


def _retrieve_subscription(subscription_id: str) -> Any:
    secret = str(current_app.config.get("STRIPE_SECRET_KEY") or "").strip()
    if not secret:
        raise StripeWebhookError("STRIPE_SECRET_KEY não está configurada.")
    return stripe.Subscription.retrieve(subscription_id, api_key=secret)


def _find_subscription(subscription_id: str) -> Subscription | None:
    return Subscription.query.filter_by(
        provider=PROVIDER, provider_subscription_id=subscription_id
    ).first()


def _configured_price_id() -> str:
    price_id = str(current_app.config.get("STRIPE_PRO_PRICE_ID") or "").strip()
    if not price_id:
        raise StripeWebhookError("STRIPE_PRO_PRICE_ID não está configurada.")
    return price_id


def _subscription_price_id(data: Any) -> str:
    items = _value(_value(data, "items", {}) or {}, "data", []) or []
    if len(items) != 1:
        raise StripeWebhookError("Assinatura PRO deve possuir exatamente um item.")
    return _id(_value(items[0], "price"))


def _subscription_period_end(data: Any) -> datetime | None:
    direct = _timestamp(_value(data, "current_period_end"))
    if direct:
        return direct
    items = _value(_value(data, "items", {}) or {}, "data", []) or []
    ends = [_timestamp(_value(item, "current_period_end")) for item in items]
    return max((end for end in ends if end), default=None)


def _invoice_subscription_id(invoice: Any) -> str:
    direct = _id(_value(invoice, "subscription"))
    if direct:
        return direct
    parent = _value(invoice, "parent", {}) or {}
    details = _value(parent, "subscription_details", {}) or {}
    return _id(_value(details, "subscription"))


def _invoice_period_end(invoice: Any) -> datetime | None:
    lines = _value(_value(invoice, "lines", {}) or {}, "data", []) or []
    ends = [
        _timestamp(_value(_value(line, "period", {}) or {}, "end")) for line in lines
    ]
    return max(
        (end for end in ends if end), default=_timestamp(_value(invoice, "period_end"))
    )


def _event_object(event: Any) -> Any:
    return _value(_value(event, "data", {}) or {}, "object", {}) or {}


def _id(value: Any) -> str:
    if isinstance(value, str):
        return value
    return str(_value(value, "id") or "")


def _timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    try:
        return datetime.fromtimestamp(int(value), timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _as_utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def _value(data: Any, key: str, default: Any = None) -> Any:
    if isinstance(data, dict):
        return data.get(key, default)
    return getattr(data, key, default)
