from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from Blueprints.services.payments.mercado_pago_gateway import (
    MercadoPagoGateway,
    MercadoPagoGatewayError,
)
from Blueprints.services.payments.plans import PaymentPlan, get_payment_plan
from Blueprints.services.subscription.subscription_service import (
    synchronize_user_pro_status,
)
from extensions import db
from models import PaymentPlanMapping, Subscription

PROVIDER = "mercado_pago"
OPEN_SUBSCRIPTION_STATUSES = {"creating", "pending", "active", "paused"}


class InvalidIdempotencyKeyError(ValueError):
    pass


class CheckoutConflictError(RuntimeError):
    pass


class SubscriptionNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class CheckoutResult:
    checkout_url: str
    subscription_id: int
    reused: bool


def create_checkout(
    usuario,
    plan_code: object,
    idempotency_key: object,
    back_url: str,
    *,
    gateway: MercadoPagoGateway | None = None,
) -> CheckoutResult:
    plan = get_payment_plan(plan_code)
    normalized_key = normalize_idempotency_key(idempotency_key)
    payment_gateway = gateway or MercadoPagoGateway()

    lock_checkout_for_user(usuario.id)
    existing = Subscription.query.filter_by(
        provider=PROVIDER, checkout_idempotency_key=normalized_key
    ).first()
    if existing is not None:
        return reuse_checkout(existing, usuario.id, plan)

    open_subscription = (
        Subscription.query.filter(
            Subscription.user_id == usuario.id,
            Subscription.provider == PROVIDER,
            Subscription.provider_plan_id.isnot(None),
            Subscription.status.in_(OPEN_SUBSCRIPTION_STATUSES),
        )
        .order_by(Subscription.id.desc())
        .first()
    )
    if open_subscription is not None:
        if open_subscription.checkout_url and open_subscription.status in {
            "creating",
            "pending",
        }:
            return CheckoutResult(
                open_subscription.checkout_url, open_subscription.id, True
            )
        raise CheckoutConflictError("Você já possui uma assinatura em andamento.")

    legacy_entitlement = Subscription.query.filter(
        Subscription.user_id == usuario.id,
        Subscription.provider == PROVIDER,
        Subscription.provider_plan_id.is_(None),
        Subscription.status == "active",
        Subscription.paid_through_at.isnot(None),
        Subscription.paid_through_at > utc_now(),
    ).first()
    if legacy_entitlement is not None:
        raise CheckoutConflictError(
            "Seu acesso PRO atual ainda está vigente. Assine após o vencimento."
        )

    subscription = Subscription(
        user_id=usuario.id,
        provider=PROVIDER,
        external_reference=f"boost:subscription:{uuid4()}",
        checkout_idempotency_key=normalized_key,
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
        existing = Subscription.query.filter_by(
            provider=PROVIDER, checkout_idempotency_key=normalized_key
        ).first()
        if existing is None:
            raise
        return reuse_checkout(existing, usuario.id, plan)

    try:
        mapping = ensure_provider_plan(plan, back_url, payment_gateway)
        checkout = payment_gateway.create_subscription(
            build_subscription_payload(
                subscription,
                usuario.email,
                plan,
                mapping.provider_plan_id,
                back_url,
            )
        )
    except (MercadoPagoGatewayError, CheckoutConflictError):
        subscription.status = "error"
        subscription.updated_at = utc_now()
        db.session.commit()
        raise

    subscription.provider_plan_id = mapping.provider_plan_id
    subscription.provider_subscription_id = checkout.subscription_id
    subscription.checkout_url = checkout.checkout_url
    subscription.status = map_subscription_status(checkout.status)
    subscription.started_at = utc_now()
    subscription.updated_at = utc_now()
    db.session.commit()
    return CheckoutResult(checkout.checkout_url, subscription.id, False)


def ensure_provider_plan(
    plan: PaymentPlan,
    back_url: str,
    gateway: MercadoPagoGateway,
) -> PaymentPlanMapping:
    lock_provider_plan(plan.code)
    mapping = PaymentPlanMapping.query.filter_by(
        provider=PROVIDER, plan=plan.code
    ).first()
    if mapping is not None:
        if Decimal(mapping.amount) != plan.amount or mapping.currency != plan.currency:
            raise CheckoutConflictError(
                "O plano recorrente precisa ser sincronizado antes da venda."
            )
        return mapping

    provider_plan = gateway.create_subscription_plan(
        build_subscription_plan_payload(plan, back_url)
    )
    mapping = PaymentPlanMapping(
        provider=PROVIDER,
        plan=plan.code,
        provider_plan_id=provider_plan.plan_id,
        amount=plan.amount,
        currency=plan.currency,
    )
    db.session.add(mapping)
    db.session.commit()
    return mapping


def cancel_current_subscription(
    usuario,
    *,
    gateway: MercadoPagoGateway | None = None,
) -> Subscription:
    subscription = (
        Subscription.query.filter(
            Subscription.user_id == usuario.id,
            Subscription.provider == PROVIDER,
            Subscription.provider_plan_id.isnot(None),
            Subscription.provider_subscription_id.isnot(None),
            Subscription.status.in_(OPEN_SUBSCRIPTION_STATUSES),
        )
        .order_by(Subscription.id.desc())
        .with_for_update()
        .first()
    )
    if subscription is None:
        raise SubscriptionNotFoundError("Nenhuma assinatura ativa foi encontrada.")

    provider_data = (gateway or MercadoPagoGateway()).cancel_subscription(
        subscription.provider_subscription_id
    )
    if (
        str(provider_data.get("id") or "") != subscription.provider_subscription_id
        or str(provider_data.get("external_reference") or "")
        != subscription.external_reference
        or str(provider_data.get("status") or "").lower() != "cancelled"
    ):
        raise MercadoPagoGatewayError(
            "O provedor não confirmou o cancelamento da assinatura."
        )

    subscription.status = "cancelled"
    subscription.canceled_at = utc_now()
    subscription.updated_at = utc_now()
    synchronize_user_pro_status(usuario, False)
    db.session.commit()
    return subscription


def reuse_checkout(
    subscription: Subscription, user_id: int, plan: PaymentPlan
) -> CheckoutResult:
    if subscription.user_id != user_id or subscription.plan != plan.code:
        raise CheckoutConflictError("Chave de idempotência já utilizada.")
    if subscription.checkout_url and subscription.status in {"pending", "creating"}:
        return CheckoutResult(subscription.checkout_url, subscription.id, True)
    if subscription.status == "creating":
        raise CheckoutConflictError("Assinatura em criação. Aguarde alguns instantes.")
    raise CheckoutConflictError("Use uma nova tentativa para iniciar a assinatura.")


def build_subscription_plan_payload(
    plan: PaymentPlan, back_url: str
) -> dict[str, object]:
    return {
        "reason": plan.title,
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": float(plan.amount),
            "currency_id": plan.currency,
        },
        "payment_methods_allowed": {
            "payment_types": [{"id": "credit_card"}],
        },
        "back_url": back_url,
    }


def build_subscription_payload(
    subscription: Subscription,
    payer_email: str,
    plan: PaymentPlan,
    provider_plan_id: str,
    back_url: str,
) -> dict[str, object]:
    return {
        "preapproval_plan_id": provider_plan_id,
        "reason": plan.title,
        "external_reference": subscription.external_reference,
        "payer_email": payer_email,
        "back_url": back_url,
    }


def map_subscription_status(provider_status: object) -> str:
    return {
        "pending": "pending",
        "authorized": "active",
        "paused": "paused",
        "cancelled": "cancelled",
    }.get(str(provider_status or "").strip().lower(), "pending")


def normalize_idempotency_key(value: object) -> str:
    try:
        return str(UUID(str(value or "").strip()))
    except (ValueError, AttributeError) as exc:
        raise InvalidIdempotencyKeyError(
            "Envie uma chave de idempotência UUID válida."
        ) from exc


def lock_checkout_for_user(user_id: int) -> None:
    execute_postgres_advisory_lock(f"subscription-checkout:user:{user_id}")


def lock_provider_plan(plan_code: str) -> None:
    execute_postgres_advisory_lock(f"subscription-plan:{plan_code}")


def execute_postgres_advisory_lock(lock_key: str) -> None:
    bind = db.session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        db.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": lock_key},
        )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
