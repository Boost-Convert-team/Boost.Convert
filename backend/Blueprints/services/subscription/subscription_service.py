from dataclasses import dataclass
from datetime import datetime, timezone

from extensions import db
from models import Subscription

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
    entitlement = find_active_paid_entitlement(user_id, now)
    if entitlement is not None:
        return ProAccessState(
            True,
            "payment",
            entitlement.paid_through_at,
        )

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
    return find_active_paid_entitlement(user_id, now or utc_now()) is not None


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
    return Subscription.query.filter_by(user_id=user_id).first() is None


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
