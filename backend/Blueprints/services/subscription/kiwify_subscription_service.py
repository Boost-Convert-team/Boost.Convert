from __future__ import annotations

import json
import logging

from extensions import db
from models import Usuario


KIWIFY_EVENT_FIELDS = ("webhook_event_type", "event", "type")
KIWIFY_PLAN_BY_EVENT = {
    "order_approved": "pro",
    "subscription_renewed": "pro",
    "subscription_canceled": "free",
    "chargeback": "free",
    "compra_reembolsada": "free",
    "refund": "free",
}
SUBSCRIPTION_STATUS_BY_PLAN = {"pro": "active", "free": "inactive"}


def sync_kiwify_user_plan(payload: dict[str, object], logger: logging.Logger) -> None:
    """Apply Kiwify subscription events to the local user plan.

    Example: sync_kiwify_user_plan({"webhook_event_type": "order_approved"}, logger)
    """
    event = _extract_kiwify_event(payload)
    email = _extract_kiwify_customer_email(payload)
    next_plan = KIWIFY_PLAN_BY_EVENT.get(event)
    if not email or next_plan is None:
        _log_kiwify_sync_skip(logger, event, email)
        return

    user = _find_kiwify_user_by_email(email)
    if user is None:
        _log_kiwify_user_not_found(logger, event, email)
        return

    _update_kiwify_user_plan(user, next_plan)
    _log_kiwify_user_plan_updated(logger, event, email, next_plan)


def _extract_kiwify_event(payload: dict[str, object]) -> str:
    for field_name in KIWIFY_EVENT_FIELDS:
        event = payload.get(field_name)
        if isinstance(event, str):
            return event.strip()
    return ""


def _extract_kiwify_customer_email(payload: dict[str, object]) -> str:
    customer = payload.get("Customer")
    if not isinstance(customer, dict):
        return ""
    email = customer.get("email")
    if not isinstance(email, str):
        return ""
    return email.strip().lower()


def _find_kiwify_user_by_email(email: str) -> Usuario | None:
    return Usuario.query.filter_by(email=email).first()


def _update_kiwify_user_plan(user: Usuario, next_plan: str) -> None:
    user.plano = next_plan
    user.status_assinatura = SUBSCRIPTION_STATUS_BY_PLAN[next_plan]
    db.session.commit()


def _log_kiwify_sync_skip(logger: logging.Logger, event: str, email: str) -> None:
    log_data = {"event": "kiwify_webhook_sync_skipped", "kiwify_event": event, "email": email}
    logger.debug(json.dumps(log_data, ensure_ascii=False))


def _log_kiwify_user_not_found(logger: logging.Logger, event: str, email: str) -> None:
    log_data = {"event": "kiwify_webhook_user_not_found", "kiwify_event": event, "email": email}
    logger.info(json.dumps(log_data, ensure_ascii=False))


def _log_kiwify_user_plan_updated(
    logger: logging.Logger,
    event: str,
    email: str,
    next_plan: str,
) -> None:
    log_data = {
        "event": "kiwify_webhook_user_plan_updated",
        "kiwify_event": event,
        "email": email,
        "plan": next_plan,
    }
    logger.info(json.dumps(log_data, ensure_ascii=False))
