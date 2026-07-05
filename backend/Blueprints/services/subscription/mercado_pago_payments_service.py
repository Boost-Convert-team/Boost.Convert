from __future__ import annotations

import json
from datetime import timedelta
from typing import Any
from urllib.parse import urljoin

from flask import current_app

from extensions import db
from models import Payment, Subscription, Usuario
from Blueprints.services.subscription.mercado_pago_service import (
    MercadoPagoError,
    PROVIDER,
    build_external_reference,
    extract_user_id_from_external_reference,
    get_base_url,
    get_plan_price,
    get_string,
    mercado_pago_request,
    parse_decimal,
    utc_now,
)


PRO_PLAN_NAME = "BoostConvert PRO"
ONE_TIME_ACCESS_DAYS = 30
PIX_PAYMENT_METHOD = "pix"
DEBIT_PAYMENT_METHOD = "debit_card"
CREDIT_PAYMENT_METHOD = "credit_card"
ONE_TIME_PAYMENT_METHODS = {PIX_PAYMENT_METHOD, DEBIT_PAYMENT_METHOD, CREDIT_PAYMENT_METHOD}
APPROVED_PAYMENT_STATUSES = {"approved", "processed"}
FAILED_PAYMENT_STATUSES = {
    "cancelled",
    "canceled",
    "rejected",
    "expired",
    "refunded",
    "charged_back",
}


def create_one_time_checkout_preference(usuario: Usuario) -> dict[str, Any]:
    """Create a Checkout Pro preference where Mercado Pago renders payment methods."""
    price = get_plan_price()
    base_url = get_base_url()
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
            "excluded_payment_types": [{"id": "ticket"}, {"id": "atm"}],
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
) -> Payment:
    provider_payment_id = get_string(provider_data, "id")
    if not provider_payment_id:
        raise MercadoPagoError("Pagamento do Mercado Pago sem ID.")

    payment = Payment.query.filter_by(
        provider=PROVIDER,
        provider_payment_id=provider_payment_id,
    ).first()
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

    payment.user_id = user.id
    payment.user = user
    payment.provider_subscription_id = get_string(provider_data, "preapproval_id") or None
    payment.status = get_string(provider_data, "status") or "pending"
    payment.payment_method = requested_payment_method or payment.payment_method or detect_payment_method(provider_data)
    payment.amount = parse_decimal(provider_data.get("transaction_amount"))
    payment.currency = get_string(provider_data, "currency_id") or "BRL"
    payment.updated_at = utc_now()

    if activate_access:
        apply_confirmed_payment_status(payment, provider_data)
    return payment


def apply_confirmed_payment_status(payment: Payment, provider_data: dict[str, Any]) -> None:
    status = payment.status.lower()
    provider_payment_type = get_string(provider_data, "payment_type_id")
    detected_method = detect_payment_method(provider_data)

    if status in APPROVED_PAYMENT_STATUSES and detected_method in ONE_TIME_PAYMENT_METHODS:
        payment.payment_method = detected_method
        if payment.premium_expires_at is None:
            payment.premium_expires_at = utc_now() + timedelta(days=ONE_TIME_ACCESS_DAYS)
        payment.user.plano = "pro"
        payment.user.status_assinatura = "active"
        return

    if status in APPROVED_PAYMENT_STATUSES and provider_payment_type != DEBIT_PAYMENT_METHOD:
        current_app.logger.warning(
            "mercado_pago_payment_approved_with_unexpected_method payment_id=%s method=%s type=%s",
            payment.provider_payment_id,
            detected_method,
            provider_payment_type,
        )


def find_user_for_payment(provider_data: dict[str, Any], payment: Payment | None) -> Usuario | None:
    user_id = extract_user_id_from_external_reference(provider_data.get("external_reference"))
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
