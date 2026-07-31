from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin
from uuid import UUID, uuid4

from flask import current_app
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Payment, Subscription, Usuario
from Blueprints.services.subscription.mercado_pago_service import (
    MercadoPagoError,
    PROVIDER,
    PRO_PLAN_CODE,
    build_external_reference,
    extract_user_id_from_external_reference,
    get_base_url,
    get_plan_price,
    get_string,
    mercado_pago_request,
    parse_decimal,
    parse_provider_datetime,
    utc_now,
)
from Blueprints.services.subscription.subscription_service import (
    APPROVED_PAYMENT_STATUSES,
    as_utc,
    synchronize_user_pro_status,
)


PRO_PLAN_NAME = "BoostConvert PRO"
ONE_TIME_ACCESS_DAYS = 30
PIX_PAYMENT_METHOD = "pix"
DEBIT_PAYMENT_METHOD = "debit_card"
CREDIT_PAYMENT_METHOD = "credit_card"
ONE_TIME_PAYMENT_METHODS = {PIX_PAYMENT_METHOD, DEBIT_PAYMENT_METHOD, CREDIT_PAYMENT_METHOD}
FAILED_PAYMENT_STATUSES = {
    "cancelled",
    "canceled",
    "rejected",
    "expired",
    "refunded",
    "charged_back",
}
CREATING_PAYMENT_STATUS = "creating"


def create_one_time_checkout_preference(
    usuario: Usuario,
    credit_card_only: bool = False,
) -> dict[str, Any]:
    """Create a Checkout Pro preference where Mercado Pago renders payment methods."""
    price = get_plan_price()
    base_url = get_base_url()
    excluded_payment_types = [{"id": "ticket"}, {"id": "atm"}]
    if credit_card_only:
        excluded_payment_types.extend(
            {"id": payment_type}
            for payment_type in (
                "account_money",
                "bank_transfer",
                "debit_card",
                "digital_currency",
                "prepaid_card",
            )
        )
    payload = {
        "items": [
            {
                "id": "boostconvert-pro-30-days",
                "title": PRO_PLAN_NAME,
                "description": f"{PRO_PLAN_NAME} - 30 dias",
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(price),
            }
        ],
        "payer": {"email": usuario.email},
        "external_reference": build_external_reference(usuario.id),
        "notification_url": urljoin(f"{base_url}/", "webhooks/mercado-pago"),
        "back_urls": {
            "success": urljoin(f"{base_url}/", "conta"),
            "pending": urljoin(f"{base_url}/", "conta"),
            "failure": urljoin(f"{base_url}/", "planos"),
        },
        "auto_return": "approved",
        "binary_mode": False,
        "payment_methods": {
            "excluded_payment_types": excluded_payment_types,
            "installments": 1,
        },
        "statement_descriptor": "BOOSTCONVERT",
    }
    data = mercado_pago_request("POST", "/checkout/preferences", json_payload=payload)
    checkout_url = select_preference_checkout_url(data)
    preference_id = get_string(data, "id")
    if not checkout_url or not preference_id:
        raise MercadoPagoError("Mercado Pago nao retornou a URL do checkout.")

    current_app.logger.info(
        json.dumps(
            {
                "event": "mercado_pago_checkout_preference_created",
                "user_id": usuario.id,
                "preference_id": preference_id,
            },
            ensure_ascii=False,
        )
    )
    return {
        "ok": True,
        "provider": PROVIDER,
        "plan_name": PRO_PLAN_NAME,
        "checkout_url": checkout_url,
        "preference_id": preference_id,
        "status": "created",
    }


def create_pix_payment(
    usuario: Usuario,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Create and persist a pending Pix payment without granting PRO access."""
    price = get_plan_price()
    base_url = get_base_url()
    external_reference = build_external_reference(usuario.id)
    normalized_idempotency_key = normalize_idempotency_key(idempotency_key)
    payment = get_or_create_pix_attempt(
        usuario,
        normalized_idempotency_key,
        external_reference,
        price,
    )
    if has_complete_pix_checkout_data(payment):
        return build_pix_payment_response(payment)

    payload = {
        "transaction_amount": float(price),
        "description": f"{PRO_PLAN_NAME} - 30 dias",
        "payment_method_id": PIX_PAYMENT_METHOD,
        "payer": {"email": usuario.email},
        "external_reference": external_reference,
        "notification_url": urljoin(f"{base_url}/", "api/webhooks/mercadopago"),
        "metadata": {
            "user_id": usuario.id,
            "plan": PRO_PLAN_CODE,
        },
    }
    data = mercado_pago_request(
        "POST",
        "/v1/payments",
        json_payload=payload,
        extra_headers={"X-Idempotency-Key": normalized_idempotency_key},
    )
    point_of_interaction = data.get("point_of_interaction")
    transaction_data = (
        point_of_interaction.get("transaction_data", {})
        if isinstance(point_of_interaction, dict)
        else {}
    )
    if not isinstance(transaction_data, dict) or not transaction_data:
        transaction_data = data.get("transaction_data")
    if not isinstance(transaction_data, dict):
        transaction_data = {}

    qr_code = get_string(transaction_data, "qr_code")
    qr_code_base64 = get_string(transaction_data, "qr_code_base64")
    ticket_url = get_string(transaction_data, "ticket_url")
    if not qr_code or not qr_code_base64 or not ticket_url:
        raise MercadoPagoError("Mercado Pago nao retornou todos os dados do Pix.")

    payment = upsert_payment_from_provider_data(
        data,
        user=usuario,
        requested_payment_method=PIX_PAYMENT_METHOD,
        activate_access=False,
        existing_payment=payment,
    )
    payment.pix_qr_code = qr_code
    payment.pix_qr_code_base64 = qr_code_base64
    payment.pix_ticket_url = ticket_url
    db.session.commit()

    current_app.logger.info(
        json.dumps(
            {
                "event": "mercado_pago_pix_payment_created",
                "user_id": usuario.id,
                "provider_payment_id": payment.provider_payment_id,
                "status": payment.status,
            },
            ensure_ascii=False,
        )
    )
    return build_pix_payment_response(payment)


def get_or_create_pix_attempt(
    usuario: Usuario,
    idempotency_key: str,
    external_reference: str,
    price: Decimal,
) -> Payment:
    payment = Payment.query.filter_by(
        provider=PROVIDER,
        idempotency_key=idempotency_key,
    ).first()
    if payment is not None:
        validate_pix_attempt_owner(payment, usuario)
        return payment

    payment = Payment(
        user_id=usuario.id,
        provider=PROVIDER,
        external_reference=external_reference,
        plan=PRO_PLAN_CODE,
        idempotency_key=idempotency_key,
        payment_method=PIX_PAYMENT_METHOD,
        status=CREATING_PAYMENT_STATUS,
        amount=price,
        currency="BRL",
    )
    db.session.add(payment)
    try:
        db.session.commit()
        return payment
    except IntegrityError:
        db.session.rollback()
        payment = Payment.query.filter_by(
            provider=PROVIDER,
            idempotency_key=idempotency_key,
        ).first()
        if payment is None:
            raise MercadoPagoError("Nao foi possivel iniciar o pagamento Pix.")
        validate_pix_attempt_owner(payment, usuario)
        return payment


def validate_pix_attempt_owner(payment: Payment, usuario: Usuario) -> None:
    if payment.user_id != usuario.id or payment.payment_method != PIX_PAYMENT_METHOD:
        raise MercadoPagoError("Chave de idempotencia pertence a outro pagamento.")


def normalize_idempotency_key(value: str | None) -> str:
    if value:
        try:
            return str(UUID(str(value).strip()))
        except (ValueError, AttributeError):
            pass
    return str(uuid4())


def has_complete_pix_checkout_data(payment: Payment) -> bool:
    return bool(
        payment.provider_payment_id
        and payment.pix_qr_code
        and payment.pix_qr_code_base64
        and payment.pix_ticket_url
    )


def build_pix_payment_response(payment: Payment) -> dict[str, Any]:
    amount = payment.amount or get_plan_price()
    return {
        "ok": True,
        "provider": PROVIDER,
        "plan": payment.plan or PRO_PLAN_CODE,
        "plan_name": PRO_PLAN_NAME,
        "payment_id": payment.provider_payment_id,
        "status": payment.status,
        "amount": f"{amount:.2f}",
        "qr_code": payment.pix_qr_code,
        "qr_code_base64": payment.pix_qr_code_base64,
        "ticket_url": payment.pix_ticket_url,
    }


def select_preference_checkout_url(provider_data: dict[str, Any]) -> str:
    access_token = str(current_app.config.get("MERCADO_PAGO_ACCESS_TOKEN") or "")
    init_point = get_string(provider_data, "init_point")
    sandbox_init_point = get_string(provider_data, "sandbox_init_point")
    if access_token.startswith("TEST-"):
        return sandbox_init_point or init_point
    return init_point or sandbox_init_point


def get_payment(payment_id: str) -> dict[str, Any]:
    return mercado_pago_request("GET", f"/v1/payments/{payment_id}")


def process_confirmed_payment(payment_id: str) -> Payment:
    data = get_payment(payment_id)
    return upsert_payment_from_provider_data(data, activate_access=True)


def upsert_payment_from_provider_data(
    provider_data: dict[str, Any],
    user: Usuario | None = None,
    requested_payment_method: str | None = None,
    activate_access: bool = False,
    existing_payment: Payment | None = None,
) -> Payment:
    provider_payment_id = get_string(provider_data, "id")
    if not provider_payment_id:
        raise MercadoPagoError("Pagamento do Mercado Pago sem ID.")

    provider_payment = Payment.query.filter_by(
        provider=PROVIDER,
        provider_payment_id=provider_payment_id,
    ).first()
    if (
        provider_payment is not None
        and existing_payment is not None
        and provider_payment.id != existing_payment.id
    ):
        raise MercadoPagoError("Pagamento do Mercado Pago ja vinculado a outra tentativa.")

    payment = provider_payment or existing_payment
    external_user_id = extract_user_id_from_external_reference(
        provider_data.get("external_reference")
    )
    if (
        payment is not None
        and external_user_id is not None
        and payment.user_id != external_user_id
    ):
        raise MercadoPagoError("Referencia externa nao corresponde ao pagamento salvo.")
    if user is not None and external_user_id is not None and user.id != external_user_id:
        raise MercadoPagoError("Referencia externa nao corresponde ao usuario.")

    user = user or find_user_for_payment(provider_data, payment)
    if user is None:
        raise MercadoPagoError("Usuario do pagamento nao encontrado.")

    if payment is None:
        payment = Payment(
            user_id=user.id,
            provider=PROVIDER,
            provider_payment_id=provider_payment_id,
            payment_method=requested_payment_method or detect_payment_method(provider_data),
        )
        db.session.add(payment)
    elif payment.provider_payment_id and payment.provider_payment_id != provider_payment_id:
        raise MercadoPagoError("Tentativa Pix ja vinculada a outro pagamento.")

    previous_payment_method = payment.payment_method
    detected_payment_method = detect_payment_method(provider_data)
    payment.user_id = user.id
    payment.user = user
    payment.provider_payment_id = provider_payment_id
    payment.provider_subscription_id = (
        get_string(provider_data, "preapproval_id")
        or payment.provider_subscription_id
    )
    payment.external_reference = (
        get_string(provider_data, "external_reference")
        or payment.external_reference
        or build_external_reference(user.id)
    )
    payment.plan = get_provider_plan(provider_data) or payment.plan or PRO_PLAN_CODE
    payment.status = get_string(provider_data, "status") or "pending"
    if requested_payment_method:
        payment.payment_method = requested_payment_method
    elif detected_payment_method != "unknown":
        payment.payment_method = detected_payment_method
    payment.amount = parse_decimal(provider_data.get("transaction_amount"))
    payment.currency = get_string(provider_data, "currency_id") or "BRL"
    payment.payment_created_at = (
        parse_provider_datetime(provider_data.get("date_created"))
        or payment.payment_created_at
    )
    payment.updated_at = utc_now()

    if activate_access:
        apply_confirmed_payment_status(
            payment,
            provider_data,
            previous_payment_method=previous_payment_method,
        )
    return payment


def apply_confirmed_payment_status(
    payment: Payment,
    provider_data: dict[str, Any],
    previous_payment_method: str,
) -> None:
    status = payment.status.lower()
    provider_payment_type = get_string(provider_data, "payment_type_id")
    detected_method = detect_payment_method(provider_data)
    subscription = get_payment_subscription(payment)

    if subscription is not None:
        subscription.latest_payment_status = status
        subscription.provider_payment_id = payment.provider_payment_id

    if status in APPROVED_PAYMENT_STATUSES and detected_method in ONE_TIME_PAYMENT_METHODS:
        validate_approved_pro_payment(
            payment,
            provider_data,
            detected_method,
            previous_payment_method,
        )
        payment.payment_method = detected_method
        payment.approved_at = (
            parse_provider_datetime(provider_data.get("date_approved"))
            or payment.approved_at
            or utc_now()
        )
        paid_through_at = get_payment_paid_through_at(subscription, payment.approved_at)
        if payment.premium_expires_at is None or as_utc(payment.premium_expires_at) < paid_through_at:
            payment.premium_expires_at = paid_through_at
        if subscription is not None:
            current_paid_through = as_utc(subscription.paid_through_at)
            if current_paid_through is None or current_paid_through < paid_through_at:
                subscription.paid_through_at = paid_through_at
        synchronize_user_pro_status(payment.user, persist=False)
        return

    if status in APPROVED_PAYMENT_STATUSES and provider_payment_type != DEBIT_PAYMENT_METHOD:
        current_app.logger.warning(
            "mercado_pago_payment_approved_with_unexpected_method payment_id=%s method=%s type=%s",
            payment.provider_payment_id,
            detected_method,
            provider_payment_type,
        )

    synchronize_user_pro_status(payment.user, persist=False)


def get_payment_subscription(payment: Payment) -> Subscription | None:
    if not payment.provider_subscription_id:
        return None
    return Subscription.query.filter_by(
        provider=PROVIDER,
        provider_subscription_id=payment.provider_subscription_id,
    ).first()


def get_payment_paid_through_at(
    subscription: Subscription | None,
    approved_at: datetime,
) -> datetime:
    if subscription is not None:
        next_payment_at = as_utc(subscription.next_payment_at)
        if next_payment_at is not None and next_payment_at > approved_at:
            return next_payment_at
    return approved_at + timedelta(days=ONE_TIME_ACCESS_DAYS)


def validate_approved_pro_payment(
    payment: Payment,
    provider_data: dict[str, Any],
    detected_method: str,
    previous_payment_method: str,
) -> None:
    expected_reference = build_external_reference(payment.user_id)
    if get_string(provider_data, "external_reference") != expected_reference:
        raise MercadoPagoError("Referencia externa do pagamento invalida.")

    if previous_payment_method not in {"", "unknown", detected_method}:
        raise MercadoPagoError("Metodo do pagamento diverge da tentativa criada.")

    amount = parse_decimal(provider_data.get("transaction_amount"))
    if amount is None or amount != get_expected_payment_amount(payment):
        raise MercadoPagoError("Valor do pagamento nao corresponde ao plano PRO.")

    if get_string(provider_data, "currency_id").upper() != "BRL":
        raise MercadoPagoError("Moeda do pagamento nao corresponde ao plano PRO.")

    provider_plan = get_provider_plan(provider_data)
    if provider_plan and provider_plan != PRO_PLAN_CODE:
        raise MercadoPagoError("Plano do pagamento nao corresponde ao BoostConvert PRO.")


def get_expected_payment_amount(payment: Payment) -> Decimal:
    if payment.provider_subscription_id:
        subscription = Subscription.query.filter_by(
            provider=PROVIDER,
            provider_subscription_id=payment.provider_subscription_id,
        ).first()
        if subscription is not None and subscription.amount is not None:
            return Decimal(subscription.amount).quantize(Decimal("0.01"))
    return get_plan_price()


def get_provider_plan(provider_data: dict[str, Any]) -> str:
    metadata = provider_data.get("metadata")
    if not isinstance(metadata, dict):
        return ""
    return get_string(metadata, "plan")


def find_user_for_payment(provider_data: dict[str, Any], payment: Payment | None) -> Usuario | None:
    user_id = extract_user_id_from_external_reference(provider_data.get("external_reference"))
    if payment is not None and user_id is not None and payment.user_id != user_id:
        return None
    if user_id is not None:
        return db.session.get(Usuario, user_id)
    if payment is not None:
        return payment.user
    preapproval_id = get_string(provider_data, "preapproval_id")
    if preapproval_id:
        subscription = Subscription.query.filter_by(
            provider=PROVIDER,
            provider_subscription_id=preapproval_id,
        ).first()
        if subscription is not None:
            return subscription.user
    return None


def detect_payment_method(provider_data: dict[str, Any]) -> str:
    payment_method_id = get_string(provider_data, "payment_method_id")
    payment_type_id = get_string(provider_data, "payment_type_id")
    if payment_method_id == PIX_PAYMENT_METHOD:
        return PIX_PAYMENT_METHOD
    if payment_type_id == DEBIT_PAYMENT_METHOD:
        return DEBIT_PAYMENT_METHOD
    return payment_type_id or payment_method_id or "unknown"
