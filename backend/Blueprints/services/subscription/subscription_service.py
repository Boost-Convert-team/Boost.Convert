from datetime import datetime, timezone

from models import Payment, Subscription


ACTIVE_SUBSCRIPTION_STATUSES = {"authorized", "active", "approved"}
APPROVED_PAYMENT_STATUSES = {"approved", "processed"}


def has_active_pro_subscription(usuario):
    if usuario is None: return False
    if usuario.plano != "pro" or usuario.status_assinatura != "active": return False

    user_id = getattr(usuario, "id", None)
    if user_id is None: return True

    try:
        if has_active_recurring_subscription(user_id): return True
        if has_active_one_time_payment(user_id): return True
        return has_legacy_active_pro_without_payment_records(user_id)
    except RuntimeError:
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
