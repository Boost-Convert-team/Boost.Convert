from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urljoin
from uuid import UUID

import requests
from flask import current_app, request
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import PaymentWebhookEvent, Subscription, Usuario
from Blueprints.services.subscription.subscription_service import (
    ACTIVE_SUBSCRIPTION_STATUSES,
    APPROVED_PAYMENT_STATUSES,
    as_utc,
    synchronize_user_pro_status,
)


MERCADO_PAGO_API_BASE_URL = "https://api.mercadopago.com"
PROVIDER = "mercado_pago"
EXTERNAL_REFERENCE_PREFIX = "boost:user:"
PAYMENT_EXTERNAL_REFERENCE_PREFIX = "boost:payment:"
PRO_PLAN_NAME = "BoostConvert PRO"
PRO_PLAN_CODE = "BOOSTCONVERT_PRO"
INACTIVE_SUBSCRIPTION_STATUSES = {
    "cancelled",
    "canceled",
    "paused",
    "rejected",
    "expired",
    "inactive",
}
FAILED_PAYMENT_STATUSES = {
    "cancelled",
    "canceled",
    "rejected",
    "expired",
    "refunded",
    "charged_back",
}


class MercadoPagoError(RuntimeError):
    """Raised when Mercado Pago cannot create or confirm a payment."""


class MercadoPagoTimeoutError(MercadoPagoError):
    """Raised when the provider did not answer within the configured timeout."""


class MercadoPagoHTTPError(MercadoPagoError):
    """Provider HTTP error with a safe application status and optional retry hint."""

    def __init__(
        self,
        message: str,
        *,
        provider_status: int,
        public_status: int,
        retry_after: str | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_status = provider_status
        self.public_status = public_status
        self.retry_after = retry_after


class MercadoPagoInvalidResponseError(MercadoPagoError):
    """Raised when the provider response cannot be safely interpreted."""


@dataclass(frozen=True)
class MercadoPagoWebhookResult:
    status: str
    event_type: str
    resource_id: str
    duplicate: bool = False


def create_monthly_subscription(usuario: Usuario) -> dict[str, str]:
    """Create a pending monthly subscription and return Mercado Pago checkout URL."""
    price = get_plan_price()
    base_url = get_base_url()
    payload = {
        "reason": PRO_PLAN_NAME,
        "external_reference": build_external_reference(usuario.id),
        "payer_email": usuario.email,
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": float(price),
            "currency_id": "BRL",
        },
        "back_url": urljoin(f"{base_url}/", "conta"),
        "status": "pending",
    }

    data = mercado_pago_request("POST", "/preapproval", json_payload=payload)
    checkout_url = get_string(data, "init_point")
    subscription_id = get_string(data, "id")
    if not checkout_url or not subscription_id:
        raise MercadoPagoError("Mercado Pago nao retornou a URL de assinatura.")

    upsert_subscription_from_provider_data(data)
    db.session.commit()
    current_app.logger.info(
        json.dumps(
            {
                "event": "mercado_pago_subscription_created",
                "user_id": usuario.id,
                "provider_subscription_id": subscription_id,
            },
            ensure_ascii=False,
        )
    )
    return {
        "checkout_url": checkout_url,
        "subscription_id": subscription_id,
        "status": get_string(data, "status") or "pending",
        "plan_name": PRO_PLAN_NAME,
    }


def process_mercado_pago_webhook(payload: dict[str, Any]) -> MercadoPagoWebhookResult:
    event_type = extract_webhook_event_type(payload)
    resource_id = extract_webhook_resource_id(payload)
    event_id = extract_webhook_event_id(payload)

    if event_id and is_duplicate_webhook_event(event_id):
        return MercadoPagoWebhookResult("duplicate", event_type, resource_id, duplicate=True)

    try:
        result = (
            MercadoPagoWebhookResult("ignored", event_type, resource_id)
            if not event_type or not resource_id
            else dispatch_mercado_pago_webhook(payload, event_type, resource_id)
        )
        record_webhook_event(payload, event_id, result)
        db.session.commit()
        return result
    except IntegrityError:
        # A unique provider event ID is the final concurrency guard when two
        # workers receive the same notification at the same time.
        db.session.rollback()
        if event_id and is_duplicate_webhook_event(event_id):
            return MercadoPagoWebhookResult(
                "duplicate", event_type, resource_id, duplicate=True
            )
        raise


def dispatch_mercado_pago_webhook(
    payload: dict[str, Any],
    event_type: str,
    resource_id: str,
) -> MercadoPagoWebhookResult:
    if event_type == "subscription_preapproval":
        subscription_data = get_subscription(resource_id)
        upsert_subscription_from_provider_data(subscription_data)
        return MercadoPagoWebhookResult("processed", event_type, resource_id)

    if event_type == "subscription_authorized_payment":
        invoice_data = get_authorized_payment(resource_id)
        preapproval_id = get_string(invoice_data, "preapproval_id")
        payment = invoice_data.get("payment") if isinstance(invoice_data.get("payment"), dict) else {}
        payment_id = get_string(payment, "id")

        if preapproval_id:
            subscription_data = get_subscription(preapproval_id)
            subscription = upsert_subscription_from_provider_data(subscription_data, payment_id)
            if payment_id:
                from Blueprints.services.subscription.mercado_pago_payments_service import (
                    process_confirmed_payment,
                )

                confirmed_payment = process_confirmed_payment(payment_id)
                apply_payment_status(subscription, confirmed_payment.status)
            else:
                subscription.latest_payment_status = (
                    get_string(payment, "status") or "pending"
                )
                synchronize_user_pro_status(subscription.user, persist=False)
            return MercadoPagoWebhookResult("processed", event_type, resource_id)

    if event_type == "payment":
        from Blueprints.services.subscription.mercado_pago_payments_service import (
            process_confirmed_payment,
        )

        process_confirmed_payment(resource_id)
        return MercadoPagoWebhookResult("processed", event_type, resource_id)

    current_app.logger.debug(
        json.dumps(
            {
                "event": "mercado_pago_webhook_ignored",
                "type": event_type,
                "resource_id": resource_id,
                "payload_id": payload.get("id"),
            },
            ensure_ascii=False,
        )
    )
    return MercadoPagoWebhookResult("ignored", event_type, resource_id)


def validate_mercado_pago_webhook_signature(payload: dict[str, Any]) -> bool:
    secret = current_app.config.get("MERCADO_PAGO_WEBHOOK_SECRET")
    if not secret:
        current_app.logger.error("mercado_pago_webhook_secret_not_configured")
        return False

    x_signature = request.headers.get("x-signature", "")
    x_request_id = request.headers.get("x-request-id", "")
    data_id = get_signature_data_id(payload)
    payload_resource_id = extract_webhook_resource_id(payload)
    if not x_signature or not x_request_id or not data_id:
        return False
    if payload_resource_id and payload_resource_id != data_id:
        return False
    return validate_signature_parts(
        x_signature,
        x_request_id,
        data_id,
        secret,
        tolerance_seconds=int(
            current_app.config.get("MERCADO_PAGO_WEBHOOK_TOLERANCE_SECONDS", 300)
        ),
    )


def validate_signature_parts(
    x_signature: str,
    x_request_id: str,
    data_id: str,
    secret: str,
    tolerance_seconds: int | None = None,
    now_timestamp: int | None = None,
) -> bool:
    signature_parts = parse_signature_header(x_signature)
    ts = signature_parts.get("ts", "")
    received_hash = signature_parts.get("v1", "")
    if not ts or not received_hash:
        return False

    if tolerance_seconds is not None and not is_webhook_timestamp_fresh(
        ts,
        tolerance_seconds,
        now_timestamp=now_timestamp,
    ):
        return False

    manifest = build_webhook_manifest(data_id, x_request_id, ts)
    expected_hash = hmac.new(
        secret.encode("utf-8"),
        manifest.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_hash, received_hash)


def is_webhook_timestamp_fresh(
    timestamp: str,
    tolerance_seconds: int,
    *,
    now_timestamp: int | None = None,
) -> bool:
    try:
        parsed_timestamp = int(timestamp)
    except (TypeError, ValueError):
        return False
    if parsed_timestamp <= 0 or tolerance_seconds < 0:
        return False
    now_timestamp = int(time.time()) if now_timestamp is None else int(now_timestamp)
    return abs(now_timestamp - parsed_timestamp) <= tolerance_seconds


def parse_signature_header(x_signature: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for chunk in x_signature.split(","):
        key, separator, value = chunk.partition("=")
        if separator:
            parts[key.strip()] = value.strip()
    return parts


def build_webhook_manifest(data_id: str, x_request_id: str, ts: str) -> str:
    manifest = ""
    if data_id:
        manifest += f"id:{data_id.lower()};"
    if x_request_id:
        manifest += f"request-id:{x_request_id};"
    if ts:
        manifest += f"ts:{ts};"
    return manifest


def get_signature_data_id(payload: dict[str, Any]) -> str:
    return (
        request.args.get("data.id", "")
        or request.args.get("data_id", "")
        or extract_webhook_resource_id(payload)
    )


def get_subscription(subscription_id: str) -> dict[str, Any]:
    return mercado_pago_request("GET", f"/preapproval/{subscription_id}")


def get_authorized_payment(authorized_payment_id: str) -> dict[str, Any]:
    return mercado_pago_request("GET", f"/authorized_payments/{authorized_payment_id}")


def mercado_pago_request(
    method: str,
    path: str,
    json_payload: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
    expected_response_types: tuple[type, ...] = (dict,),
) -> Any:
    access_token = current_app.config.get("MERCADO_PAGO_ACCESS_TOKEN")
    if not access_token:
        raise MercadoPagoError("MERCADO_PAGO_ACCESS_TOKEN nao configurado.")

    url = f"{MERCADO_PAGO_API_BASE_URL}{path}"
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)

        response = requests.request(
            method,
            url,
            headers=headers,
            json=json_payload,
            timeout=15,
        )
    except requests.Timeout as exc:
        raise MercadoPagoTimeoutError("Mercado Pago demorou para responder.") from exc
    except requests.RequestException as exc:
        raise MercadoPagoError("Falha ao conectar com Mercado Pago.") from exc

    if response.status_code >= 400:
        provider_error_code = get_provider_error_code(response)
        current_app.logger.warning(
            json.dumps(
                {
                    "event": "mercado_pago_api_error",
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "provider_error_code": provider_error_code,
                },
                ensure_ascii=False,
            )
        )
        public_status, message = classify_provider_http_error(response.status_code)
        raise MercadoPagoHTTPError(
            message,
            provider_status=response.status_code,
            public_status=public_status,
            retry_after=get_safe_retry_after(response),
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise MercadoPagoInvalidResponseError(
            "Mercado Pago retornou uma resposta invalida."
        ) from exc

    if not isinstance(data, expected_response_types):
        raise MercadoPagoInvalidResponseError(
            "Mercado Pago retornou uma resposta inesperada."
        )
    return data


def classify_provider_http_error(status_code: int) -> tuple[int, str]:
    if status_code in {400, 422}:
        return 422, "Mercado Pago recusou os dados do pagamento."
    if status_code in {401, 403}:
        return 502, "Mercado Pago recusou a autenticacao da integracao."
    if status_code == 409:
        return 409, "Mercado Pago informou conflito no pagamento."
    if status_code == 429:
        return 503, "Mercado Pago esta temporariamente limitando requisicoes."
    if status_code >= 500:
        return 503, "Mercado Pago esta temporariamente indisponivel."
    return 502, "Mercado Pago recusou a operacao."


def get_provider_error_code(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return "unavailable"
    if not isinstance(payload, dict):
        return "unavailable"
    value = payload.get("error") or payload.get("code") or payload.get("status")
    if value is None:
        cause = payload.get("cause")
        if isinstance(cause, list) and cause and isinstance(cause[0], dict):
            value = cause[0].get("code")
    normalized = str(value or "unavailable").strip()
    return normalized[:80]


def get_safe_retry_after(response: requests.Response) -> str | None:
    value = str(response.headers.get("Retry-After") or "").strip()
    if not value.isdigit():
        return None
    return str(min(int(value), 3600))


def upsert_subscription_from_provider_data(
    provider_data: dict[str, Any],
    provider_payment_id: str | None = None,
) -> Subscription:
    provider_subscription_id = get_string(provider_data, "id")
    if not provider_subscription_id:
        raise MercadoPagoError("Assinatura do Mercado Pago sem ID.")

    subscription = Subscription.query.filter_by(
        provider=PROVIDER,
        provider_subscription_id=provider_subscription_id,
    ).first()
    user = find_user_for_subscription(provider_data, subscription)
    if user is None:
        raise MercadoPagoError("Usuario da assinatura nao encontrado.")

    if subscription is None:
        subscription = Subscription(
            user_id=user.id,
            provider=PROVIDER,
            provider_subscription_id=provider_subscription_id,
        )
        db.session.add(subscription)

    auto_recurring = provider_data.get("auto_recurring")
    if not isinstance(auto_recurring, dict):
        auto_recurring = {}

    subscription.user_id = user.id
    subscription.external_reference = (
        get_string(provider_data, "external_reference")
        or subscription.external_reference
        or build_external_reference(user.id)
    )
    subscription.plan = subscription.plan or PRO_PLAN_CODE
    subscription.status = get_string(provider_data, "status") or "pending"
    subscription.provider_payment_id = provider_payment_id or subscription.provider_payment_id
    subscription.amount = parse_decimal(auto_recurring.get("transaction_amount"))
    subscription.currency = get_string(auto_recurring, "currency_id") or "BRL"
    subscription.next_payment_at = parse_provider_datetime(provider_data.get("next_payment_date"))
    subscription.updated_at = utc_now()

    apply_subscription_status(user, subscription)
    return subscription


def apply_subscription_status(user: Usuario, subscription: Subscription) -> None:
    status = subscription.status.lower()
    if status in ACTIVE_SUBSCRIPTION_STATUSES:
        subscription.started_at = subscription.started_at or utc_now()
        subscription.canceled_at = None
        synchronize_user_pro_status(user, persist=False)
        return

    if status in INACTIVE_SUBSCRIPTION_STATUSES:
        subscription.canceled_at = subscription.canceled_at or utc_now()
        synchronize_user_pro_status(user, persist=False)


def apply_payment_status(subscription: Subscription, payment_status: str) -> None:
    status = payment_status.lower()
    subscription.latest_payment_status = status
    if status in APPROVED_PAYMENT_STATUSES:
        subscription.started_at = subscription.started_at or utc_now()
        paid_through_at = get_subscription_paid_through_at(subscription)
        current_paid_through = as_utc(subscription.paid_through_at)
        if current_paid_through is None or current_paid_through < paid_through_at:
            subscription.paid_through_at = paid_through_at
        synchronize_user_pro_status(subscription.user, persist=False)
        return

    if status in FAILED_PAYMENT_STATUSES:
        synchronize_user_pro_status(subscription.user, persist=False)


def get_subscription_paid_through_at(subscription: Subscription) -> datetime:
    now = utc_now()
    next_payment_at = as_utc(subscription.next_payment_at)
    if next_payment_at is not None and next_payment_at > now:
        return next_payment_at
    return now + timedelta(days=30)


def find_user_for_subscription(
    provider_data: dict[str, Any],
    subscription: Subscription | None,
) -> Usuario | None:
    user_id = extract_user_id_from_external_reference(provider_data.get("external_reference"))
    if user_id is not None:
        return db.session.get(Usuario, user_id)
    if subscription is not None:
        return subscription.user
    return None


def record_webhook_event(
    payload: dict[str, Any],
    event_id: str,
    result: MercadoPagoWebhookResult,
) -> None:
    if event_id and is_duplicate_webhook_event(event_id):
        return
    db.session.add(
        PaymentWebhookEvent(
            provider=PROVIDER,
            provider_event_id=event_id or None,
            event_type=result.event_type or "unknown",
            resource_id=result.resource_id or None,
            status=result.status,
            payload=sanitize_webhook_payload(payload),
        )
    )


def sanitize_webhook_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist delivery metadata only, never an arbitrary provider payload."""
    data = payload.get("data")
    return {
        "id": str(payload.get("id") or "")[:120],
        "type": str(payload.get("type") or payload.get("topic") or "")[:80],
        "action": str(payload.get("action") or "")[:80],
        "data": {
            "id": str(data.get("id") or "")[:120]
            if isinstance(data, dict)
            else ""
        },
        "live_mode": payload.get("live_mode")
        if isinstance(payload.get("live_mode"), bool)
        else None,
    }


def is_duplicate_webhook_event(event_id: str) -> bool:
    return (
        PaymentWebhookEvent.query.filter_by(
            provider=PROVIDER,
            provider_event_id=event_id,
        ).first()
        is not None
    )


def extract_webhook_event_type(payload: dict[str, Any]) -> str:
    event_type = payload.get("type") or request.args.get("type") or payload.get("topic")
    return event_type.strip() if isinstance(event_type, str) else ""


def extract_webhook_resource_id(payload: dict[str, Any]) -> str:
    data = payload.get("data")
    if isinstance(data, dict):
        data_id = data.get("id")
        if data_id is not None:
            return str(data_id).strip()
    data_id = request.args.get("data.id") or request.args.get("data_id")
    if data_id:
        return data_id.strip()
    return ""


def extract_webhook_event_id(payload: dict[str, Any]) -> str:
    # The notification ID is stable across delivery retries. x-request-id
    # identifies one HTTP delivery and therefore is only a fallback.
    event_id = payload.get("id") or request.headers.get("x-request-id", "")
    return str(event_id).strip() if event_id else ""


def build_external_reference(user_id: int) -> str:
    return f"{EXTERNAL_REFERENCE_PREFIX}{user_id}"


def build_payment_external_reference(user_id: int, attempt_id: str) -> str:
    normalized_attempt_id = str(UUID(str(attempt_id).strip()))
    return f"{PAYMENT_EXTERNAL_REFERENCE_PREFIX}{normalized_attempt_id}:user:{user_id}"


def extract_payment_attempt_id(value: object) -> str | None:
    if not isinstance(value, str) or not value.startswith(
        PAYMENT_EXTERNAL_REFERENCE_PREFIX
    ):
        return None
    attempt_value, separator, user_part = value.removeprefix(
        PAYMENT_EXTERNAL_REFERENCE_PREFIX
    ).partition(":user:")
    if not separator or not user_part.isdigit():
        return None
    try:
        return str(UUID(attempt_value))
    except (ValueError, AttributeError):
        return None


def extract_user_id_from_external_reference(value: object) -> int | None:
    if not isinstance(value, str):
        return None
    if value.startswith(PAYMENT_EXTERNAL_REFERENCE_PREFIX):
        attempt_id = extract_payment_attempt_id(value)
        if attempt_id is None:
            return None
        _, _, user_part = value.rpartition(":user:")
        try:
            return int(user_part)
        except ValueError:
            return None
    if not value.startswith(EXTERNAL_REFERENCE_PREFIX):
        return None
    try:
        return int(value.removeprefix(EXTERNAL_REFERENCE_PREFIX))
    except ValueError:
        return None


def get_plan_price() -> Decimal:
    raw_price = current_app.config.get("MERCADO_PAGO_PLAN_PRICE", "19.90")
    try:
        price = Decimal(str(raw_price).replace(",", ".")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise MercadoPagoError("MERCADO_PAGO_PLAN_PRICE invalido.") from exc
    if price <= 0:
        raise MercadoPagoError("MERCADO_PAGO_PLAN_PRICE precisa ser maior que zero.")
    return price


def get_base_url() -> str:
    configured_base_url = current_app.config.get("BASE_URL")
    if configured_base_url:
        return configured_base_url.rstrip("/")
    return request.url_root.rstrip("/")


def get_string(source: dict[str, Any], key: str) -> str:
    value = source.get(key)
    return str(value).strip() if value is not None else ""


def parse_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value).replace(",", ".")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def parse_provider_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized_value = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized_value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
