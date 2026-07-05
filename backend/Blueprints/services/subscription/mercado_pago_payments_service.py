from __future__ import annotations

import json
from datetime import timedelta
from typing import Any
from uuid import uuid4

from flask import current_app

from extensions import db
from models import Payment, Subscription, Usuario
from Blueprints.services.subscription.mercado_pago_service import (
    MercadoPagoError,
    PROVIDER,
    build_external_reference,
    extract_user_id_from_external_reference,
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
APPROVED_PAYMENT_STATUSES = {"approved", "processed"}
FAILED_PAYMENT_STATUSES = {
    "cancelled",
    "canceled",
    "rejected",
    "expired",
    "refunded",
    "charged_back",
}


def create_pix_payment(usuario: Usuario) -> dict[str, Any]:
    price = get_plan_price()
    payload = {
        "transaction_amount": float(price),
        "description": f"{PRO_PLAN_NAME} - 30 dias",
        "payment_method_id": PIX_PAYMENT_METHOD,
        "external_reference": build_external_reference(usuario.id),
        "payer": {"email": usuario.email},
    }
    data = create_payment(payload)
    payment = upsert_payment_from_provider_data(
        data,
        user=usuario,
        requested_payment_method=PIX_PAYMENT_METHOD,
        activate_access=False,
    )
    db.session.commit()
    current_app.logger.info(
        json.dumps(
            {
                "event": "mercado_pago_pix_payment_created",
                "user_id": usuario.id,
                "provider_payment_id": payment.provider_payment_id,
            },
            ensure_ascii=False,
        )
    )
    return build_pix_checkout_response(data)


def create_debit_card_payment(usuario: Usuario, form_data: dict[str, Any]) -> dict[str, Any]:
    price = get_plan_price()
    payload = build_debit_payment_payload(usuario, form_data, price)
    data = create_payment(payload)
    payment = upsert_payment_from_provider_data(
        data,
        user=usuario,
        requested_payment_method=DEBIT_PAYMENT_METHOD,
        activate_access=False,
    )
    db.session.commit()
    current_app.logger.info(
        json.dumps(
            {
                "event": "mercado_pago_debit_payment_created",
                "user_id": usuario.id,
                "provider_payment_id": payment.provider_payment_id,
                "status": payment.status,
            },
            ensure_ascii=False,
        )
    )
    return {
        "ok": True,
        "provider": PROVIDER,
        "plan_name": PRO_PLAN_NAME,
        "payment_id": payment.provider_payment_id,
        "status": payment.status,
        "message": "Pagamento recebido. O BoostConvert PRO sera liberado apos confirmacao do webhook.",
    }


def create_payment(payload: dict[str, Any]) -> dict[str, Any]:
    return mercado_pago_request(
        "POST",
        "/v1/payments",
        json_payload=payload,
        extra_headers={"X-Idempotency-Key": str(uuid4())},
    )


def get_payment(payment_id: str) -> dict[str, Any]:
    return mercado_pago_request("GET", f"/v1/payments/{payment_id}")


def process_confirmed_payment(payment_id: str) -> Payment:
    data = get_payment(payment_id)
    return upsert_payment_from_provider_data(data, activate_access=True)


def build_debit_payment_payload(
    usuario: Usuario,
    form_data: dict[str, Any],
    price: object,
) -> dict[str, Any]:
    token = get_string(form_data, "token")
    payment_method_id = get_string(form_data, "payment_method_id")
    issuer_id = get_string(form_data, "issuer_id")
    installments = int(form_data.get("installments") or 1)
    payer = form_data.get("payer") if isinstance(form_data.get("payer"), dict) else {}
    identification = payer.get("identification") if isinstance(payer.get("identification"), dict) else {}

    if not token or not payment_method_id:
        raise MercadoPagoError("Dados do cartao de debito incompletos.")

    payload: dict[str, Any] = {
        "transaction_amount": float(price),
        "token": token,
        "installments": installments,
        "payment_method_id": payment_method_id,
        "description": f"{PRO_PLAN_NAME} - 30 dias",
        "external_reference": build_external_reference(usuario.id),
        "payer": {
            "email": usuario.email,
        },
    }
    if issuer_id:
        payload["issuer_id"] = issuer_id
    if identification:
        payload["payer"]["identification"] = {
            "type": get_string(identification, "type"),
            "number": get_string(identification, "number"),
        }
    return payload


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

    if status in APPROVED_PAYMENT_STATUSES and detected_method in {PIX_PAYMENT_METHOD, DEBIT_PAYMENT_METHOD}:
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


def build_pix_checkout_response(provider_data: dict[str, Any]) -> dict[str, Any]:
    payment_id = get_string(provider_data, "id")
    point_of_interaction = provider_data.get("point_of_interaction")
    if not isinstance(point_of_interaction, dict):
        point_of_interaction = {}
    transaction_data = point_of_interaction.get("transaction_data")
    if not isinstance(transaction_data, dict):
        transaction_data = {}
    return {
        "ok": True,
        "provider": PROVIDER,
        "plan_name": PRO_PLAN_NAME,
        "payment_id": payment_id,
        "status": get_string(provider_data, "status") or "pending",
        "qr_code": get_string(transaction_data, "qr_code"),
        "qr_code_base64": get_string(transaction_data, "qr_code_base64"),
        "ticket_url": get_string(transaction_data, "ticket_url"),
        "message": "Pague o PIX e aguarde a confirmacao do webhook para liberar o BoostConvert PRO.",
    }
