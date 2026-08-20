from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

import mercadopago
import requests
from flask import current_app
from mercadopago.config import RequestOptions
from mercadopago.errors import MercadoPagoError as SDKMercadoPagoError


class MercadoPagoConfigurationError(RuntimeError):
    pass


class MercadoPagoRequestError(RuntimeError):
    def __init__(
        self,
        operation: str,
        status: int | None,
        provider_error: object,
        provider_message: object = "",
        provider_causes: object = None,
        request_id: object = "",
    ) -> None:
        self.operation = _safe_log_value(operation)
        self.status = status
        self.provider_error = _safe_log_value(provider_error)
        # Compatibility for callers that still read the former attribute name.
        self.provider_code = self.provider_error
        self.provider_message = _safe_log_value(provider_message, fallback="none", limit=400)
        self.provider_causes = _safe_provider_causes(provider_causes)
        self.request_id = _safe_log_value(request_id, fallback="none")
        super().__init__("Falha na comunicação com o Mercado Pago.")

    @property
    def provider_causes_log(self) -> str:
        return json.dumps(
            self.provider_causes,
            ensure_ascii=True,
            separators=(",", ":"),
        )


class MercadoPagoGateway:
    """Thin boundary around the official Mercado Pago Python SDK."""

    def __init__(self, sdk: Any | None = None) -> None:
        if sdk is not None:
            self.sdk = sdk
            return

        access_token = str(
            current_app.config.get("MERCADOPAGO_ACCESS_TOKEN") or ""
        ).strip()
        if not access_token:
            raise MercadoPagoConfigurationError("MERCADOPAGO_ACCESS_TOKEN missing")

        timeout = float(
            current_app.config.get("MERCADOPAGO_REQUEST_TIMEOUT_SECONDS", 10.0)
        )
        self.sdk = mercadopago.SDK(
            access_token,
            request_options=RequestOptions(connection_timeout=timeout),
        )

    def create_subscription(
        self, payload: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        options = RequestOptions(custom_headers={"x-idempotency-key": idempotency_key})
        return self._call(
            "subscription_create",
            lambda: self.sdk.preapproval().create(payload, options),
        )

    def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        resource_id = _resource_id(subscription_id)
        return self._call(
            "subscription_get",
            lambda: self.sdk.preapproval().get(resource_id),
        )

    def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        resource_id = _resource_id(subscription_id)
        return self._call(
            "subscription_cancel",
            lambda: self.sdk.preapproval().update(resource_id, {"status": "canceled"}),
        )

    def get_invoice(self, invoice_id: str) -> dict[str, Any]:
        resource_id = _resource_id(invoice_id)
        return self._call(
            "invoice_get",
            lambda: self.sdk.invoice().get(resource_id),
        )

    def search_invoices(self, subscription_id: str) -> list[dict[str, Any]]:
        resource_id = _resource_id(subscription_id)
        response = self._call(
            "invoice_search",
            lambda: self.sdk.invoice().search({"preapproval_id": resource_id}),
        )
        results = response.get("results")
        if not isinstance(results, list) or not all(
            isinstance(item, dict) for item in results
        ):
            raise MercadoPagoRequestError("invoice_search", None, "invalid_response")
        return results

    @staticmethod
    def _call(operation: str, request_call: Callable[[], Any]) -> dict[str, Any]:
        try:
            result = request_call()
            if hasattr(result, "raise_for_status"):
                result.raise_for_status()
        except SDKMercadoPagoError as exc:
            details = _sdk_error_details(exc)
            raise MercadoPagoRequestError(
                operation,
                int(exc.status_code) if exc.status_code else None,
                details["error"],
                details["message"],
                details["causes"],
                details["request_id"],
            ) from exc
        except requests.Timeout as exc:
            raise MercadoPagoRequestError(operation, None, "timeout") from exc
        except requests.RequestException as exc:
            raise MercadoPagoRequestError(operation, None, "network_error") from exc

        if not isinstance(result, dict):
            raise MercadoPagoRequestError(operation, None, "invalid_response")
        status = result.get("status")
        body = result.get("response")
        if not isinstance(status, int) or not 200 <= status < 300:
            details = _response_error_details(body)
            raise MercadoPagoRequestError(
                operation,
                status if isinstance(status, int) else None,
                details["error"],
                details["message"],
                details["causes"],
                details["request_id"],
            )
        if not isinstance(body, dict):
            raise MercadoPagoRequestError(operation, status, "invalid_response")
        return body


def checkout_error_status(error: MercadoPagoRequestError) -> int:
    if error.status in {400, 402, 422}:
        return 422
    if error.status in {409, 423}:
        return 409
    if error.status is not None and error.status >= 500:
        return 502
    return 503


def _resource_id(value: object) -> str:
    normalized = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", normalized):
        raise MercadoPagoRequestError("resource_validate", None, "invalid_resource_id")
    return normalized


def _response_error_details(body: object) -> dict[str, object]:
    if not isinstance(body, dict):
        return {
            "error": "invalid_response",
            "message": "",
            "causes": [],
            "request_id": "",
        }
    cause = body.get("cause")
    first_cause = cause[0] if isinstance(cause, list) and cause else {}
    if not isinstance(first_cause, dict):
        first_cause = {}
    return {
        "error": (
            body.get("error")
            or body.get("code")
            or first_cause.get("code")
            or body.get("status")
            or "unknown"
        ),
        "message": body.get("message") or first_cause.get("description") or "",
        "causes": cause,
        "request_id": body.get("request_id") or "",
    }


def _sdk_error_details(exc: SDKMercadoPagoError) -> dict[str, object]:
    response = exc.response if isinstance(exc.response, dict) else {}
    details = _response_error_details(response)
    causes = exc.causes if isinstance(exc.causes, list) else details["causes"]
    first_cause = causes[0] if causes and isinstance(causes[0], dict) else {}
    return {
        "error": (
            exc.error
            or response.get("code")
            or first_cause.get("code")
            or response.get("status")
            or type(exc).__name__
        ),
        "message": exc.message or details["message"],
        "causes": causes,
        "request_id": exc.request_id or response.get("request_id") or "",
    }


_SENSITIVE_KEY_VALUE = re.compile(
    r"(?i)\b(authorization|access[_ -]?token|card_token_id|card[_ -]?number|"
    r"security[_ -]?code|cvv|cookie|webhook[_ -]?secret)\b\s*[:=]\s*"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;}]+)"
)
_SENSITIVE_FIELD = re.compile(
    r"(?i)\b(authorization|access[_ -]?token|card_token_id|card[_ -]?number|"
    r"security[_ -]?code|cvv|cookie|webhook[_ -]?secret)\b"
)
_BEARER_CREDENTIAL = re.compile(r"(?i)\bBearer\s+[^\s,;}]+")
_MERCADO_PAGO_CREDENTIAL = re.compile(r"\b(?:APP_USR|TEST)-[A-Za-z0-9_-]+")


def _safe_log_value(
    value: object, *, fallback: str = "unknown", limit: int = 120
) -> str:
    text = " ".join(str(value or fallback).split())
    text = _BEARER_CREDENTIAL.sub("Bearer [REDACTED]", text)
    text = _SENSITIVE_KEY_VALUE.sub("[sensitive_field]=[REDACTED]", text)
    text = _SENSITIVE_FIELD.sub("[sensitive_field]", text)
    text = _MERCADO_PAGO_CREDENTIAL.sub("[REDACTED]", text)
    return text[:limit]


def _safe_provider_causes(value: object) -> tuple[dict[str, str], ...]:
    if not isinstance(value, list):
        return ()
    safe: list[dict[str, str]] = []
    for item in value[:5]:
        if not isinstance(item, dict):
            continue
        cause: dict[str, str] = {}
        for field in ("code", "description", "message"):
            if item.get(field) not in (None, ""):
                cause[field] = _safe_log_value(item[field], fallback="", limit=300)
        if cause:
            safe.append(cause)
    return tuple(safe)
