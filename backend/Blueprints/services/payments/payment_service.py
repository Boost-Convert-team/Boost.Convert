from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from flask import current_app
from sqlalchemy import or_, text
from sqlalchemy.exc import IntegrityError

from Blueprints.services.payments.mercado_pago_client import (
    MercadoPagoClient,
    MercadoPagoError,
    is_mercado_pago_checkout_url,
)
from Blueprints.services.payments.plans import PaymentPlan, get_payment_plan
from Blueprints.services.subscription.subscription_service import (
    as_utc,
    has_active_paid_entitlement,
    synchronize_user_pro_status,
)
from extensions import db
from models import Subscription

PROVIDER = "mercado_pago"
OPEN_SUBSCRIPTION_STATUSES = {"creating", "pending", "active", "paused"}
LEGACY_CHECKOUT_PREFIX = "checkout-pro:%"


class InvalidIdempotencyKeyError(ValueError):
    pass


class CheckoutConflictError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "subscription_conflict",
        can_replace: bool = False,
    ) -> None:
        self.code = code
        self.can_replace = can_replace
        super().__init__(message)


class SubscriptionNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class CheckoutResult:
    checkout_url: str
    subscription_id: int
    reused: bool


def create_subscription_checkout(
    usuario,
    plan_code: object,
    idempotency_key: object,
    back_url: str,
    *,
    replace_unpaid_subscription: bool = False,
    client: MercadoPagoClient | None = None,
) -> CheckoutResult:
    plan = get_payment_plan(plan_code)
    normalized_key = normalize_idempotency_key(idempotency_key)
    mercado_pago = client or MercadoPagoClient()

    lock_checkout_for_user(usuario.id)
    existing = Subscription.query.filter_by(
        provider=PROVIDER, checkout_idempotency_key=normalized_key
    ).first()
    if existing is not None:
        if existing.user_id != usuario.id or existing.plan != plan.code:
            raise CheckoutConflictError("Chave de idempotencia ja utilizada.")
        if existing.status not in OPEN_SUBSCRIPTION_STATUSES:
            return reuse_checkout(existing, usuario.id, plan)
        recovered_checkout = resolve_open_subscription(
            existing,
            mercado_pago,
            replace_unpaid_subscription=replace_unpaid_subscription,
        )
        if recovered_checkout is not None:
            return recovered_checkout
        existing.checkout_idempotency_key = None
        db.session.flush()

    open_subscription = (
        Subscription.query.filter(
            Subscription.user_id == usuario.id,
            Subscription.provider == PROVIDER,
            Subscription.status.in_(OPEN_SUBSCRIPTION_STATUSES),
            or_(
                Subscription.provider_subscription_id.is_(None),
                ~Subscription.provider_subscription_id.like(LEGACY_CHECKOUT_PREFIX),
            ),
        )
        .order_by(Subscription.id.desc())
        .first()
    )
    if open_subscription is not None:
        recovered_checkout = resolve_open_subscription(
            open_subscription,
            mercado_pago,
            replace_unpaid_subscription=replace_unpaid_subscription,
        )
        if recovered_checkout is not None:
            return recovered_checkout

    legacy_entitlement = Subscription.query.filter(
        Subscription.user_id == usuario.id,
        Subscription.provider == PROVIDER,
        Subscription.provider_subscription_id.like(LEGACY_CHECKOUT_PREFIX),
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
        checkout = mercado_pago.create_subscription_checkout(
            build_subscription_payload(subscription, usuario.email, plan, back_url),
            idempotency_key=normalized_key,
        )
    except MercadoPagoError:
        subscription.status = "error"
        subscription.updated_at = utc_now()
        db.session.commit()
        raise

    subscription.provider_subscription_id = checkout.subscription_id
    subscription.checkout_url = checkout.checkout_url
    subscription.status = map_subscription_status(checkout.status)
    subscription.started_at = utc_now()
    subscription.updated_at = utc_now()
    db.session.commit()
    return CheckoutResult(checkout.checkout_url, subscription.id, False)


def cancel_current_subscription(
    usuario,
    *,
    client: MercadoPagoClient | None = None,
) -> Subscription:
    subscription = (
        Subscription.query.filter(
            Subscription.user_id == usuario.id,
            Subscription.provider == PROVIDER,
            Subscription.provider_subscription_id.isnot(None),
            ~Subscription.provider_subscription_id.like(LEGACY_CHECKOUT_PREFIX),
            Subscription.status.in_(OPEN_SUBSCRIPTION_STATUSES),
        )
        .order_by(Subscription.id.desc())
        .with_for_update()
        .first()
    )
    if subscription is None:
        raise SubscriptionNotFoundError("Nenhuma assinatura ativa foi encontrada.")

    provider_data = (client or MercadoPagoClient()).cancel_subscription(
        subscription.provider_subscription_id
    )
    apply_confirmed_cancellation(subscription, provider_data)
    synchronize_user_pro_status(usuario, False)
    db.session.commit()
    return subscription


def resolve_open_subscription(
    subscription: Subscription,
    mercado_pago: MercadoPagoClient,
    *,
    replace_unpaid_subscription: bool,
) -> CheckoutResult | None:
    """Reconcile a local open record before blocking a new checkout."""
    if subscription.provider_subscription_id is None:
        if is_recent_checkout_creation(subscription):
            raise CheckoutConflictError(
                "A assinatura está sendo criada. Aguarde alguns instantes.",
                code="subscription_creating",
            )
        mark_subscription_error(subscription)
        db.session.commit()
        return None

    try:
        provider_subscription = mercado_pago.get_subscription(
            subscription.provider_subscription_id
        )
    except MercadoPagoError as exc:
        if exc.status != 404:
            raise
        mark_subscription_error(subscription)
        db.session.commit()
        return None

    try:
        reconcile_provider_subscription(
            subscription,
            provider_subscription,
            mercado_pago,
        )
    except MercadoPagoError as exc:
        if not is_replaceable_pending_checkout(
            subscription, provider_subscription, exc
        ):
            raise
        provider_data = mercado_pago.cancel_subscription(
            subscription.provider_subscription_id
        )
        apply_confirmed_cancellation(subscription, provider_data)
        synchronize_user_pro_status(subscription.user, False)
        return None

    if subscription.status == "canceled":
        db.session.commit()
        return None

    if subscription.status == "pending":
        checkout_url = str(provider_subscription.get("init_point") or "").strip()
        if not is_mercado_pago_checkout_url(checkout_url):
            raise invalid_provider_response(
                "A assinatura pendente não possui checkout válido."
            )
        if not is_recent_pending_checkout(subscription):
            provider_data = mercado_pago.cancel_subscription(
                subscription.provider_subscription_id
            )
            apply_confirmed_cancellation(subscription, provider_data)
            synchronize_user_pro_status(subscription.user, False)
            return None
        subscription.checkout_url = checkout_url
        db.session.commit()
        return CheckoutResult(checkout_url, subscription.id, True)

    if has_active_paid_entitlement(subscription.user_id):
        db.session.commit()
        raise CheckoutConflictError(
            "Seu pagamento já foi aprovado e o acesso PRO está ativo.",
            code="subscription_already_paid",
        )

    if subscription.status == "active":
        db.session.commit()
        raise CheckoutConflictError(
            "Existe uma assinatura autorizada sem pagamento confirmado.",
            code="unpaid_subscription",
        )

    if subscription.status != "paused":
        raise invalid_provider_response("Status de assinatura desconhecido.")

    if not replace_unpaid_subscription:
        db.session.commit()
        raise CheckoutConflictError(
            "Existe uma assinatura anterior sem pagamento confirmado.",
            code="unpaid_subscription",
            can_replace=True,
        )

    provider_data = mercado_pago.cancel_subscription(
        subscription.provider_subscription_id
    )
    apply_confirmed_cancellation(subscription, provider_data)
    synchronize_user_pro_status(subscription.user, False)
    db.session.commit()
    return None


def reconcile_provider_subscription(
    subscription: Subscription,
    provider_subscription: dict[str, object],
    mercado_pago: MercadoPagoClient,
) -> None:
    """Reuse the webhook's strict provider contract for checkout recovery."""
    from Blueprints.services.payments.webhook_service import (
        WebhookValidationError,
        refresh_user_access,
        synchronize_authorized_payment,
        synchronize_subscription_fields,
        validate_provider_invoice,
        validate_provider_subscription,
    )

    try:
        validate_provider_subscription(
            provider_subscription, subscription.provider_subscription_id
        )
        synchronize_subscription_fields(subscription, provider_subscription)
        if subscription.status in {"active", "paused"}:
            invoices = mercado_pago.search_authorized_payments(
                subscription.provider_subscription_id
            )
            for invoice in invoices:
                invoice_id = str(invoice.get("id") or "").strip()
                validate_provider_invoice(invoice, invoice_id, subscription)
                synchronize_authorized_payment(
                    subscription, invoice, provider_subscription
                )
        refresh_user_access(subscription)
    except (WebhookValidationError, ValueError) as exc:
        raise invalid_provider_response(str(exc)) from exc


def apply_confirmed_cancellation(
    subscription: Subscription, provider_data: dict[str, object]
) -> None:
    if (
        str(provider_data.get("id") or "") != subscription.provider_subscription_id
        or str(provider_data.get("external_reference") or "")
        != subscription.external_reference
        or str(provider_data.get("status") or "").lower()
        not in {"canceled", "cancelled"}
    ):
        raise invalid_provider_response(
            "Mercado Pago não confirmou o cancelamento.",
            operation="subscription_cancel",
        )

    subscription.status = "canceled"
    subscription.canceled_at = utc_now()
    subscription.updated_at = utc_now()


def is_recent_checkout_creation(subscription: Subscription) -> bool:
    created_at = as_utc(subscription.created_at) or as_utc(subscription.updated_at)
    if created_at is None:
        return False
    timeout_seconds = int(
        current_app.config.get("PAYMENT_CHECKOUT_CREATION_TIMEOUT_SECONDS", 120)
    )
    return created_at > utc_now() - timedelta(seconds=max(timeout_seconds, 1))


def is_recent_pending_checkout(subscription: Subscription) -> bool:
    created_at = (
        as_utc(subscription.created_at)
        or as_utc(subscription.started_at)
        or as_utc(subscription.updated_at)
    )
    if created_at is None:
        return False
    timeout_seconds = int(
        current_app.config.get("PAYMENT_CHECKOUT_CREATION_TIMEOUT_SECONDS", 120)
    )
    return created_at > utc_now() - timedelta(seconds=max(timeout_seconds, 1))


def mark_subscription_error(subscription: Subscription) -> None:
    subscription.status = "error"
    subscription.updated_at = utc_now()


def is_replaceable_pending_checkout(
    subscription: Subscription,
    provider_subscription: dict[str, object],
    error: MercadoPagoError,
) -> bool:
    """Allow a new checkout only for an unfunded legacy pending resource."""
    return (
        error.provider_code == "invalid_response"
        and str(provider_subscription.get("id") or "")
        == subscription.provider_subscription_id
        and str(provider_subscription.get("external_reference") or "")
        == subscription.external_reference
        and str(provider_subscription.get("status") or "").strip().lower() == "pending"
        and not provider_subscription.get("payment_method_id")
        and not provider_subscription.get("card_id")
        and subscription.paid_through_at is None
    )


def invalid_provider_response(
    message: str, *, operation: str = "subscription_reconcile"
) -> MercadoPagoError:
    return MercadoPagoError(
        operation=operation,
        endpoint="/preapproval/{id}",
        status=None,
        provider_code="invalid_response",
        provider_message=message,
    )


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


def build_subscription_payload(
    subscription: Subscription,
    payer_email: str,
    plan: PaymentPlan,
    back_url: str,
) -> dict[str, object]:
    return {
        "reason": plan.title,
        "external_reference": subscription.external_reference,
        "payer_email": payer_email,
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": float(plan.amount),
            "currency_id": plan.currency,
        },
        "back_url": back_url,
        "status": "pending",
    }


def map_subscription_status(provider_status: object) -> str:
    return {
        "pending": "pending",
        "authorized": "active",
        "paused": "paused",
        "canceled": "canceled",
        "cancelled": "canceled",
    }.get(str(provider_status or "").strip().lower(), "pending")


def normalize_idempotency_key(value: object) -> str:
    try:
        return str(UUID(str(value or "").strip()))
    except (ValueError, AttributeError) as exc:
        raise InvalidIdempotencyKeyError(
            "Envie uma chave de idempotência UUID válida."
        ) from exc


def lock_checkout_for_user(user_id: int) -> None:
    bind = db.session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        db.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": f"subscription-checkout:user:{user_id}"},
        )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
