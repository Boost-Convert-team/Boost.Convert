from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID, uuid4

from flask import current_app
from sqlalchemy import or_, text
from sqlalchemy.exc import IntegrityError

from Blueprints.services.payments.mercado_pago_client import (
    MercadoPagoClient,
    MercadoPagoError,
    is_mercado_pago_checkout_url,
)
from Blueprints.services.payments.plans import (
    PRO_SUBSCRIPTION_MAX_INSTALLMENTS,
    PaymentPlan,
    get_payment_plan,
)
from Blueprints.services.subscription.subscription_service import (
    as_utc,
    find_latest_paid_expiration,
    has_active_paid_entitlement,
    synchronize_user_pro_status,
)
from extensions import db
from models import Payment, Subscription

PROVIDER = "mercado_pago"
OPEN_SUBSCRIPTION_STATUSES = {"creating", "pending", "active", "paused"}
LEGACY_CHECKOUT_PREFIX = "checkout-pro:%"
CREDIT_PAYMENT_METHOD = "credit_card"
ONE_TIME_ACCESS_DAYS = 30
FINAL_PAYMENT_STATUSES = {
    "approved",
    "rejected",
    "canceled",
    "refunded",
    "charged_back",
}
CARD_REQUEST_KEYS = {
    "token",
    "payment_method_id",
    "issuer_id",
    "installments",
    "payer",
    "transaction_amount",
}


class InvalidIdempotencyKeyError(ValueError):
    pass


class CardPaymentValidationError(ValueError):
    pass


class ProviderPaymentValidationError(ValueError):
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


def create_card_payment(
    usuario,
    card_data: object,
    idempotency_key: object,
    *,
    client: MercadoPagoClient | None = None,
) -> Payment:
    """Create one logical credit-card charge without persisting card data."""
    normalized_key = normalize_idempotency_key(idempotency_key)
    validated = validate_card_request(card_data)
    mercado_pago = client or MercadoPagoClient()

    lock_payment_for_user(usuario.id)
    payment = get_or_create_payment_attempt(usuario, normalized_key)
    if payment.provider_payment_id:
        return payment
    validate_credit_payment_method(mercado_pago, validated["payment_method_id"])

    plan = get_payment_plan("PRO")
    payer: dict[str, Any] = {"email": str(usuario.email).strip().lower()}
    identification = validated["payer"].get("identification")
    if identification:
        payer["identification"] = identification
    payload: dict[str, Any] = {
        "token": validated["token"],
        "transaction_amount": float(plan.amount),
        "description": plan.title,
        "installments": validated["installments"],
        "payment_method_id": validated["payment_method_id"],
        "payer": payer,
        "external_reference": payment.external_reference,
        "notification_url": str(
            current_app.config.get("MERCADOPAGO_WEBHOOK_URL") or ""
        ).strip(),
        "metadata": {
            "user_id": usuario.id,
            "plan": plan.code,
            "attempt_id": payment.attempt_id,
        },
        "statement_descriptor": "BOOSTCONVERT",
    }
    if validated["issuer_id"]:
        payload["issuer_id"] = validated["issuer_id"]

    provider_data = mercado_pago.create_payment(payload, idempotency_key=normalized_key)
    synchronize_payment_from_provider(
        payment,
        provider_data,
        expected_payment_id=str(provider_data.get("id") or ""),
    )
    db.session.commit()
    current_app.logger.info(
        "mercadopago_payment_created user_id=%s payment_id=%s status=%s",
        usuario.id,
        payment.provider_payment_id or "none",
        payment.status,
    )
    return payment


def create_card_subscription(
    usuario,
    card_data: object,
    idempotency_key: object,
    back_url: str,
    *,
    client: MercadoPagoClient | None = None,
) -> Subscription:
    """Create the monthly PRO subscription without persisting card data."""
    plan = get_payment_plan("PRO")
    normalized_key = normalize_idempotency_key(idempotency_key)
    validated = validate_card_subscription_request(card_data)
    mercado_pago = client or MercadoPagoClient()

    lock_checkout_for_user(usuario.id)
    subscription = Subscription.query.filter_by(
        provider=PROVIDER, checkout_idempotency_key=normalized_key
    ).first()
    if subscription is not None:
        validate_subscription_attempt_owner(subscription, usuario.id, plan)
        if subscription.provider_subscription_id:
            return subscription
        validate_credit_payment_method(mercado_pago, validated["payment_method_id"])
    else:
        open_subscription = find_open_subscription(usuario.id)
        if open_subscription is not None:
            recovered = resolve_open_subscription(
                open_subscription,
                mercado_pago,
                replace_unpaid_subscription=False,
            )
            if recovered is not None:
                raise CheckoutConflictError(
                    "Existe uma assinatura anterior aguardando conclusão."
                )
        if has_active_paid_entitlement(usuario.id):
            raise CheckoutConflictError(
                "Seu acesso PRO atual ainda está vigente. Assine após o vencimento."
            )
        validate_credit_payment_method(mercado_pago, validated["payment_method_id"])

        subscription = Subscription(
            user_id=usuario.id,
            provider=PROVIDER,
            external_reference=f"boost:subscription:{usuario.id}:{normalized_key}",
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
            subscription = Subscription.query.filter_by(
                provider=PROVIDER, checkout_idempotency_key=normalized_key
            ).first()
            if subscription is None:
                raise
            validate_subscription_attempt_owner(subscription, usuario.id, plan)
            if subscription.provider_subscription_id:
                return subscription

    try:
        provider_subscription = mercado_pago.create_authorized_subscription(
            build_authorized_subscription_payload(
                subscription,
                usuario.email,
                plan,
                back_url,
                validated["token"],
            ),
            idempotency_key=normalized_key,
        )
    except MercadoPagoError:
        subscription.status = "error"
        subscription.updated_at = utc_now()
        db.session.commit()
        raise

    subscription.provider_subscription_id = provider_subscription.subscription_id
    subscription.checkout_url = None
    subscription.status = map_subscription_status(provider_subscription.status)
    subscription.started_at = subscription.started_at or utc_now()
    subscription.updated_at = utc_now()
    db.session.commit()
    current_app.logger.info(
        "mercadopago_subscription_created user_id=%s subscription_id=%s status=%s",
        usuario.id,
        subscription.provider_subscription_id,
        subscription.status,
    )
    return subscription


def validate_card_subscription_request(card_data: object) -> dict[str, str]:
    if not isinstance(card_data, dict):
        raise CardPaymentValidationError("Envie os dados do cartão em JSON.")
    if set(card_data) - CARD_REQUEST_KEYS:
        raise CardPaymentValidationError("O pagamento contém campos não permitidos.")
    if "installments" in card_data:
        try:
            installments = int(card_data["installments"])
        except (TypeError, ValueError):
            installments = 0
        if installments != PRO_SUBSCRIPTION_MAX_INSTALLMENTS:
            raise CardPaymentValidationError(
                "A assinatura mensal aceita somente pagamento em 1x."
            )
    return {
        "token": normalize_limited_string(card_data.get("token"), "token", 2048),
        "payment_method_id": normalize_limited_string(
            card_data.get("payment_method_id"), "payment_method_id", 50
        ).lower(),
    }


def validate_subscription_attempt_owner(
    subscription: Subscription, user_id: int, plan: PaymentPlan
) -> None:
    if subscription.user_id != user_id or subscription.plan != plan.code:
        raise CardPaymentValidationError(
            "Chave de idempotência pertence a outra assinatura."
        )


def validate_card_request(card_data: object) -> dict[str, Any]:
    if not isinstance(card_data, dict):
        raise CardPaymentValidationError("Envie os dados do cartão em JSON.")
    if set(card_data) - CARD_REQUEST_KEYS:
        raise CardPaymentValidationError("O pagamento contém campos não permitidos.")

    token = normalize_limited_string(card_data.get("token"), "token", 2048)
    payment_method_id = normalize_limited_string(
        card_data.get("payment_method_id"), "payment_method_id", 50
    ).lower()
    issuer_id = str(card_data.get("issuer_id") or "").strip()
    if len(issuer_id) > 50:
        raise CardPaymentValidationError("Campo issuer_id inválido.")
    try:
        installments = int(card_data.get("installments"))
    except (TypeError, ValueError):
        installments = 0
    maximum = int(current_app.config.get("MERCADOPAGO_MAX_INSTALLMENTS", 12))
    if installments < 1 or installments > maximum:
        raise CardPaymentValidationError("Quantidade de parcelas inválida.")

    payer_data = card_data.get("payer") or {}
    if not isinstance(payer_data, dict):
        raise CardPaymentValidationError("Dados do pagador inválidos.")
    identification = payer_data.get("identification")
    payer: dict[str, Any] = {}
    if identification not in (None, {}):
        if not isinstance(identification, dict):
            raise CardPaymentValidationError("Identificação do pagador inválida.")
        payer["identification"] = {
            "type": normalize_limited_string(
                identification.get("type"), "payer.identification.type", 10
            ),
            "number": normalize_limited_string(
                identification.get("number"), "payer.identification.number", 30
            ),
        }
    return {
        "token": token,
        "payment_method_id": payment_method_id,
        "issuer_id": issuer_id,
        "installments": installments,
        "payer": payer,
    }


def normalize_limited_string(value: object, field: str, maximum: int) -> str:
    normalized = str(value or "").strip()
    if not normalized or len(normalized) > maximum:
        raise CardPaymentValidationError(f"Campo {field} inválido.")
    return normalized


def validate_credit_payment_method(
    mercado_pago: MercadoPagoClient, payment_method_id: str
) -> None:
    method = next(
        (
            item
            for item in mercado_pago.get_payment_methods()
            if str(item.get("id") or "").strip().lower() == payment_method_id
        ),
        None,
    )
    if (
        method is None
        or str(method.get("payment_type_id") or "").strip().lower()
        != CREDIT_PAYMENT_METHOD
        or str(method.get("status") or "active").strip().lower() != "active"
    ):
        raise CardPaymentValidationError("Apenas cartão de crédito é aceito.")


def get_or_create_payment_attempt(usuario, idempotency_key: str) -> Payment:
    payment = Payment.query.filter_by(
        provider=PROVIDER, idempotency_key=idempotency_key
    ).first()
    if payment is not None:
        validate_payment_attempt_owner(payment, usuario.id)
        return payment

    plan = get_payment_plan("PRO")
    payment = Payment(
        user_id=usuario.id,
        provider=PROVIDER,
        external_reference=f"boost:payment:{usuario.id}:{idempotency_key}",
        plan=plan.code,
        attempt_id=idempotency_key,
        idempotency_key=idempotency_key,
        payment_method=CREDIT_PAYMENT_METHOD,
        status="creating",
        amount=plan.amount,
        currency=plan.currency,
    )
    db.session.add(payment)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        payment = Payment.query.filter_by(
            provider=PROVIDER, idempotency_key=idempotency_key
        ).first()
        if payment is None:
            raise
        validate_payment_attempt_owner(payment, usuario.id)
    return payment


def validate_payment_attempt_owner(payment: Payment, user_id: int) -> None:
    if payment.user_id != user_id or payment.payment_method != CREDIT_PAYMENT_METHOD:
        raise CardPaymentValidationError(
            "Chave de idempotência pertence a outro pagamento."
        )


def reconcile_payment(
    payment: Payment,
    *,
    client: MercadoPagoClient | None = None,
    force: bool = False,
) -> Payment:
    if payment.provider_payment_id is None or payment.status in FINAL_PAYMENT_STATUSES:
        return payment
    last_sync = as_utc(payment.last_provider_sync_at)
    minimum_interval = int(
        current_app.config.get("MERCADOPAGO_RECONCILE_INTERVAL_SECONDS", 10)
    )
    if (
        not force
        and last_sync is not None
        and last_sync > utc_now() - timedelta(seconds=max(minimum_interval, 1))
    ):
        return payment
    provider_data = (client or MercadoPagoClient()).get_payment(
        payment.provider_payment_id
    )
    synchronize_payment_from_provider(
        payment, provider_data, expected_payment_id=payment.provider_payment_id
    )
    db.session.commit()
    return payment


def synchronize_payment_from_provider(
    payment: Payment,
    provider_data: dict[str, Any],
    *,
    expected_payment_id: str,
) -> Payment:
    lock_payment_for_user(payment.user_id)
    validate_provider_payment(payment, provider_data, expected_payment_id)
    provider_status = str(provider_data.get("status") or "pending").strip().lower()
    payment.provider_payment_id = str(provider_data["id"])
    payment.status = map_payment_status(provider_status)
    payment.status_detail = str(provider_data.get("status_detail") or "")[:120]
    payment.payment_created_at = (
        parse_provider_datetime(provider_data.get("date_created"))
        or payment.payment_created_at
    )
    payment.last_provider_sync_at = utc_now()
    payment.updated_at = utc_now()

    if payment.status == "approved" and payment.premium_expires_at is None:
        approved_at = (
            parse_provider_datetime(provider_data.get("date_approved")) or utc_now()
        )
        current_expiration = find_latest_paid_expiration(
            payment.user_id, approved_at, exclude_payment_id=payment.id
        )
        base = max(approved_at, current_expiration or approved_at)
        payment.approved_at = approved_at
        payment.premium_expires_at = base + timedelta(days=ONE_TIME_ACCESS_DAYS)

    synchronize_user_pro_status(payment.user, persist=False)
    return payment


def validate_provider_payment(
    payment: Payment,
    provider_data: dict[str, Any],
    expected_payment_id: str,
) -> None:
    provider_id = str(provider_data.get("id") or "").strip()
    if not provider_id or provider_id != str(expected_payment_id or "").strip():
        raise ProviderPaymentValidationError("ID do pagamento não corresponde.")
    if str(provider_data.get("external_reference") or "").strip() != str(
        payment.external_reference or ""
    ):
        raise ProviderPaymentValidationError(
            "Referência externa do pagamento não corresponde."
        )
    try:
        amount = Decimal(str(provider_data.get("transaction_amount"))).quantize(
            Decimal("0.01")
        )
    except (InvalidOperation, TypeError) as exc:
        raise ProviderPaymentValidationError("Valor do pagamento inválido.") from exc
    if not amount.is_finite() or amount != Decimal(payment.amount):
        raise ProviderPaymentValidationError("Valor do pagamento não corresponde.")
    if str(provider_data.get("currency_id") or "").upper() != payment.currency:
        raise ProviderPaymentValidationError("Moeda do pagamento não corresponde.")
    if (
        str(provider_data.get("payment_type_id") or "").strip().lower()
        != CREDIT_PAYMENT_METHOD
    ):
        raise ProviderPaymentValidationError("Meio de pagamento não permitido.")
    if str(provider_data.get("payment_method_id") or "").strip().lower() == "":
        raise ProviderPaymentValidationError("Bandeira do pagamento ausente.")

    metadata = provider_data.get("metadata")
    if not isinstance(metadata, dict):
        raise ProviderPaymentValidationError("Metadados do pagamento ausentes.")
    if (
        str(metadata.get("attempt_id") or "") != payment.attempt_id
        or str(metadata.get("plan") or "").upper() != "PRO"
        or str(metadata.get("user_id") or "") != str(payment.user_id)
    ):
        raise ProviderPaymentValidationError("Metadados do pagamento não correspondem.")


def map_payment_status(provider_status: str) -> str:
    return {
        "approved": "approved",
        "pending": "pending",
        "in_process": "in_process",
        "rejected": "rejected",
        "cancelled": "canceled",
        "canceled": "canceled",
        "refunded": "refunded",
        "charged_back": "charged_back",
    }.get(provider_status, "pending")


def build_card_payment_response(payment: Payment) -> dict[str, object]:
    return {
        "ok": payment.status
        not in {"rejected", "canceled", "refunded", "charged_back"},
        "attempt_id": payment.attempt_id,
        "payment_id": payment.provider_payment_id,
        "status": payment.status,
        "approved": payment.status == "approved"
        and payment.premium_expires_at is not None,
    }


def parse_provider_datetime(value: object) -> datetime | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None
    return as_utc(parsed)


def lock_payment_for_user(user_id: int) -> None:
    bind = db.session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        db.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": f"card-payment:user:{user_id}"},
        )


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

    open_subscription = find_open_subscription(usuario.id)
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
    synchronize_user_pro_status(usuario)
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


def reconcile_subscription(
    subscription: Subscription,
    *,
    client: MercadoPagoClient | None = None,
) -> Subscription:
    if not subscription.provider_subscription_id:
        return subscription
    mercado_pago = client or MercadoPagoClient()
    provider_subscription = mercado_pago.get_subscription(
        subscription.provider_subscription_id
    )
    reconcile_provider_subscription(subscription, provider_subscription, mercado_pago)
    db.session.commit()
    return subscription


def find_open_subscription(user_id: int) -> Subscription | None:
    return (
        Subscription.query.filter(
            Subscription.user_id == user_id,
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
        **build_subscription_base_payload(subscription, payer_email, plan, back_url),
        "status": "pending",
    }


def build_authorized_subscription_payload(
    subscription: Subscription,
    payer_email: str,
    plan: PaymentPlan,
    back_url: str,
    card_token_id: str,
) -> dict[str, object]:
    return {
        **build_subscription_base_payload(subscription, payer_email, plan, back_url),
        "card_token_id": card_token_id,
        "status": "authorized",
    }


def build_subscription_base_payload(
    subscription: Subscription,
    payer_email: str,
    plan: PaymentPlan,
    back_url: str,
) -> dict[str, object]:
    return {
        "reason": plan.title,
        "external_reference": subscription.external_reference,
        "payer_email": str(payer_email).strip().lower(),
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": float(plan.amount),
            "currency_id": plan.currency,
        },
        "back_url": back_url,
    }


def build_card_subscription_response(
    subscription: Subscription,
) -> dict[str, object]:
    paid_through_at = as_utc(subscription.paid_through_at)
    approved = (
        subscription.status == "active"
        and paid_through_at is not None
        and paid_through_at > utc_now()
    )
    return {
        "ok": subscription.status not in {"canceled", "error"},
        "attempt_id": subscription.checkout_idempotency_key,
        "subscription_id": subscription.provider_subscription_id,
        "status": subscription.latest_payment_status or subscription.status,
        "approved": approved,
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
