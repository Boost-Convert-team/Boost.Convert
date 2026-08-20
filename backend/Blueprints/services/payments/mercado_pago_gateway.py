from __future__ import annotations

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
    def __init__(self, operation: str, status: int | None, provider_code: str) -> None:
        self.operation = operation
        self.status = status
        self.provider_code = _safe_log_value(provider_code)
        super().__init__("Falha na comunicação com o Mercado Pago.")


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
            raise MercadoPagoRequestError(
                operation,
                int(exc.status_code) if exc.status_code else None,
                str(exc.error or "sdk_error"),
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
            raise MercadoPagoRequestError(
                operation,
                status if isinstance(status, int) else None,
                _provider_code(body),
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


def _provider_code(body: object) -> str:
    if not isinstance(body, dict):
        return "invalid_response"
    cause = body.get("cause")
    first_cause = cause[0] if isinstance(cause, list) and cause else {}
    if not isinstance(first_cause, dict):
        first_cause = {}
    return str(body.get("error") or first_cause.get("code") or "unknown")


def _safe_log_value(value: object) -> str:
    return " ".join(str(value or "unknown").split())[:120]
