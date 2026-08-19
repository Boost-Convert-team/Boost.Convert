from dataclasses import dataclass
from datetime import datetime, timezone

from extensions import db
from models import Payment, Subscription

ACTIVE_SUBSCRIPTION_STATUSES = {"active"}


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

    state = get_pro_access_state(usuario)
    synchronize_user_pro_status(usuario, state.active, persist=True)
    return state.active


def get_pro_access_state(usuario, now: datetime | None = None) -> ProAccessState:
    if usuario is None:
        return ProAccessState(False, "none")

    user_id = getattr(usuario, "id", None)
    if user_id is None:
        return ProAccessState(is_user_marked_pro(usuario), "transient")

    now = now or utc_now()
    payment = find_active_one_time_payment(user_id, now)
    subscription = find_active_paid_entitlement(user_id, now)
    payment_expiration = as_utc(payment.premium_expires_at) if payment else None
    subscription_expiration = (
        as_utc(subscription.paid_through_at) if subscription else None
    )
    if payment_expiration and (
        not subscription_expiration or payment_expiration >= subscription_expiration
    ):
        return ProAccessState(
            True,
            "payment",
            payment_expiration,
        )
    if subscription_expiration:
        return ProAccessState(True, "subscription", subscription_expiration)

    if is_user_marked_pro(usuario) and has_legacy_active_pro_without_subscription(
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


def has_active_paid_entitlement(
    user_id: int,
    now: datetime | None = None,
) -> bool:
    current_time = now or utc_now()
    return (
        find_active_one_time_payment(user_id, current_time) is not None
        or find_active_paid_entitlement(user_id, current_time) is not None
    )


def find_active_one_time_payment(
    user_id: int,
    now: datetime,
    *,
    exclude_payment_id: int | None = None,
) -> Payment | None:
    query = Payment.query.filter(
        Payment.user_id == user_id,
        Payment.provider == "mercado_pago",
        Payment.payment_method == "credit_card",
        Payment.status == "approved",
        Payment.premium_expires_at.isnot(None),
        Payment.premium_expires_at > now,
    )
    if exclude_payment_id is not None:
        query = query.filter(Payment.id != exclude_payment_id)
    return query.order_by(Payment.premium_expires_at.desc()).first()


def find_latest_paid_expiration(
    user_id: int,
    now: datetime,
    *,
    exclude_payment_id: int | None = None,
) -> datetime | None:
    payment = find_active_one_time_payment(
        user_id, now, exclude_payment_id=exclude_payment_id
    )
    subscription = find_active_paid_entitlement(user_id, now)
    expirations = [
        value
        for value in (
            as_utc(payment.premium_expires_at) if payment else None,
            as_utc(subscription.paid_through_at) if subscription else None,
        )
        if value is not None
    ]
    return max(expirations) if expirations else None


def find_active_paid_entitlement(
    user_id: int,
    now: datetime,
) -> Subscription | None:
    return (
        Subscription.query.filter(
            Subscription.user_id == user_id,
            Subscription.provider == "mercado_pago",
            Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
            Subscription.paid_through_at.isnot(None),
            Subscription.paid_through_at > now,
        )
        .order_by(Subscription.paid_through_at.desc())
        .first()
    )


def has_legacy_active_pro_without_subscription(user_id: int) -> bool:
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
