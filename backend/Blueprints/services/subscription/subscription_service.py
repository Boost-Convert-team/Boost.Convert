from dataclasses import dataclass
from datetime import datetime, timezone

from extensions import db
from flask import current_app, has_app_context
from models import Payment, Subscription
from sqlalchemy.exc import SQLAlchemyError

ACTIVE_SUBSCRIPTION_STATUSES = {"authorized", "active", "approved"}
APPROVED_PAYMENT_STATUSES = {"approved"}
ACTIVE_ONE_TIME_PAYMENT_METHODS = {"credit_card", "debit_card", "pix"}
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


@dataclass(frozen=True)
class ProAccessState:
    active: bool
    source: str
    expires_at: datetime | None = None


def has_active_pro_subscription(usuario) -> bool:
    """Return paid PRO access and persist stale denormalized user flags."""
    if usuario is None:
        return False

    user_id = getattr(usuario, "id", None)
    if user_id is None:
        return is_user_marked_pro(usuario)

    try:
        state = get_pro_access_state(usuario)
        synchronize_user_pro_status(usuario, state.active, persist=True)
        return state.active
    except SQLAlchemyError as exc:
        db.session.rollback()
        if not is_missing_billing_schema_error(exc):
            raise
        log_missing_billing_schema_fallback(exc)
        return is_user_marked_pro(usuario)


def get_pro_access_state(usuario, now: datetime | None = None) -> ProAccessState:
    if usuario is None:
        return ProAccessState(False, "none")

    user_id = getattr(usuario, "id", None)
    if user_id is None:
        return ProAccessState(is_user_marked_pro(usuario), "transient")

    now = now or utc_now()
    recurring = find_active_recurring_subscription(user_id, now)
    if recurring is not None:
        return ProAccessState(True, "recurring", recurring.paid_through_at)

    payment = find_active_paid_payment(user_id, now)
    if payment is not None:
        return ProAccessState(True, "payment", payment.premium_expires_at)

    if is_user_marked_pro(usuario) and has_legacy_active_pro_without_payment_records(
        user_id
    ):
        return ProAccessState(True, "legacy")
    return ProAccessState(False, "none")


def synchronize_user_pro_status(
    usuario,
    active: bool | None = None,
    *,
    persist: bool = False,
) -> bool:
    if usuario is None:
        return False
    if active is None:
        active = get_pro_access_state(usuario).active

    desired_plan = "pro" if active else "free"
    desired_status = "active" if active else "inactive"
    changed = (
        usuario.plano != desired_plan or usuario.status_assinatura != desired_status
    )
    if changed:
        usuario.plano = desired_plan
        usuario.status_assinatura = desired_status
        if persist:
            db.session.commit()
    return active


def has_active_recurring_subscription(
    user_id: int,
    now: datetime | None = None,
) -> bool:
    return find_active_recurring_subscription(user_id, now or utc_now()) is not None


def find_active_recurring_subscription(
    user_id: int,
    now: datetime,
) -> Subscription | None:
    return (
        Subscription.query.filter(
            Subscription.user_id == user_id,
            Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
            Subscription.latest_payment_status.in_(APPROVED_PAYMENT_STATUSES),
            Subscription.paid_through_at.isnot(None),
            Subscription.paid_through_at > now,
        )
        .order_by(Subscription.paid_through_at.desc())
        .first()
    )


def has_active_one_time_payment(
    user_id: int,
    now: datetime | None = None,
) -> bool:
    return find_active_paid_payment(user_id, now or utc_now()) is not None


def find_active_paid_payment(user_id: int, now: datetime) -> Payment | None:
    return (
        Payment.query.filter(
            Payment.user_id == user_id,
            Payment.payment_method.in_(ACTIVE_ONE_TIME_PAYMENT_METHODS),
            Payment.status.in_(APPROVED_PAYMENT_STATUSES),
            Payment.premium_expires_at.isnot(None),
            Payment.premium_expires_at > now,
        )
        .order_by(Payment.premium_expires_at.desc())
        .first()
    )


def has_legacy_active_pro_without_payment_records(user_id: int) -> bool:
    return (
        Subscription.query.filter_by(user_id=user_id).first() is None
        and Payment.query.filter_by(user_id=user_id).first() is None
    )


def is_user_marked_pro(usuario) -> bool:
    return (
        getattr(usuario, "plano", None) == "pro"
        and getattr(usuario, "status_assinatura", None) == "active"
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_missing_billing_schema_error(exc: SQLAlchemyError) -> bool:
    original = getattr(exc, "orig", None)
    sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    if sqlstate in MISSING_BILLING_SCHEMA_SQLSTATES:
        return True

    message = str(exc).lower()
    return any(marker in message for marker in BILLING_TABLE_MARKERS) and any(
        marker in message for marker in MISSING_BILLING_SCHEMA_MARKERS
    )


def log_missing_billing_schema_fallback(exc: SQLAlchemyError) -> None:
    if not has_app_context():
        return

    current_app.logger.warning(
        "billing_schema_unavailable_using_legacy_pro_status error=%s",
        type(exc).__name__,
    )
