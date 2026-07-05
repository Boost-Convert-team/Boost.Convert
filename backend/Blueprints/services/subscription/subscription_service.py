from datetime import datetime, timezone

from flask import current_app, has_app_context
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import Payment, Subscription


ACTIVE_SUBSCRIPTION_STATUSES = {"authorized", "active", "approved"}
APPROVED_PAYMENT_STATUSES = {"approved", "processed"}
MISSING_BILLING_SCHEMA_SQLSTATES = {"42P01", "42703"}
MISSING_BILLING_SCHEMA_MARKERS = (
    "does not exist",
    "no such table",
    "no such column",
    "undefinedtable",
    "undefinedcolumn",
    "unknown column",
)
BILLING_TABLE_MARKERS = ("subscriptions", "payments")


def has_active_pro_subscription(usuario):
    if usuario is None: return False
    if usuario.plano != "pro" or usuario.status_assinatura != "active": return False

    user_id = getattr(usuario, "id", None)
    if user_id is None: return True

    try:
        if has_active_recurring_subscription(user_id): return True
        if has_active_one_time_payment(user_id): return True
        return has_legacy_active_pro_without_payment_records(user_id)
    except SQLAlchemyError as exc:
        db.session.rollback()
        if not is_missing_billing_schema_error(exc): raise
        log_missing_billing_schema_fallback(exc)
        return True


def has_active_recurring_subscription(user_id):
    return (
        Subscription.query.filter(
            Subscription.user_id == user_id,
            Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
        ).first()
        is not None
    )


def has_active_one_time_payment(user_id):
    return (
        Payment.query.filter(
            Payment.user_id == user_id,
            Payment.status.in_(APPROVED_PAYMENT_STATUSES),
            Payment.premium_expires_at.isnot(None),
            Payment.premium_expires_at > utc_now(),
        ).first()
        is not None
    )


def has_legacy_active_pro_without_payment_records(user_id):
    return (
        Subscription.query.filter_by(user_id=user_id).first() is None
        and Payment.query.filter_by(user_id=user_id).first() is None
    )


def utc_now():
    return datetime.now(timezone.utc)


def is_missing_billing_schema_error(exc):
    original = getattr(exc, "orig", None)
    sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    if sqlstate in MISSING_BILLING_SCHEMA_SQLSTATES:
        return True

    message = str(exc).lower()
    return any(marker in message for marker in BILLING_TABLE_MARKERS) and any(
        marker in message for marker in MISSING_BILLING_SCHEMA_MARKERS
    )


def log_missing_billing_schema_fallback(exc):
    if not has_app_context():
        return

    current_app.logger.warning(
        "billing_schema_unavailable_using_legacy_pro_status error=%s",
        type(exc).__name__,
    )
