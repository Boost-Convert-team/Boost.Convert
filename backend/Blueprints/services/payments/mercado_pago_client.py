import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests
from flask import current_app


class MercadoPagoConfigurationError(RuntimeError):
    pass


class MercadoPagoError(RuntimeError):
    def __init__(
        self,
        *,
        operation: str,
        endpoint: str,
        status: int | None,
        provider_code: str,
        provider_message: str,
    ) -> None:
        self.operation = operation
        self.endpoint = endpoint
        self.status = status
        self.provider_code = _safe_log_value(provider_code, "unknown")
        self.provider_message = _safe_log_value(
            provider_message, "Resposta desconhecida do Mercado Pago."
        )
        super().__init__(self.provider_message)


@dataclass(frozen=True)
class SubscriptionCheckout:
    subscription_id: str
    checkout_url: str
    status: str


@dataclass(frozen=True)
class AuthorizedSubscription:
    subscription_id: str
    status: str


class MercadoPagoClient:
    def __init__(self) -> None:
        self.access_token = str(
            current_app.config.get("MERCADOPAGO_ACCESS_TOKEN") or ""
        ).strip()
        if not self.access_token:
            raise MercadoPagoConfigurationError("MERCADOPAGO_ACCESS_TOKEN missing")
        self.base_url = str(current_app.config["MERCADOPAGO_API_BASE_URL"]).rstrip("/")
        self.timeout = int(
            current_app.config.get("MERCADOPAGO_REQUEST_TIMEOUT_SECONDS", 10)
        )

    def create_subscription_checkout(
        self,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> SubscriptionCheckout:
        extra_headers = (
            {"X-Idempotency-Key": idempotency_key} if idempotency_key else None
        )
        response, response_status = self._request(
            "subscription_create",
            "POST",
            "/preapproval",
            json=payload,
            extra_headers=extra_headers,
        )
        subscription_id = normalize_resource_id(response.get("id"))
        checkout_url = str(response.get("init_point") or "").strip()
        status = str(response.get("status") or "pending").strip().lower()
        if not subscription_id or not is_mercado_pago_checkout_url(checkout_url):
            raise MercadoPagoError(
                operation="subscription_create",
                endpoint="/preapproval",
                status=response_status,
                provider_code="invalid_response",
                provider_message="Mercado Pago não retornou id e init_point válidos.",
            )
        return SubscriptionCheckout(subscription_id, checkout_url, status)

    def create_authorized_subscription(
        self,
        payload: dict[str, Any],
        *,
        idempotency_key: str,
    ) -> AuthorizedSubscription:
        response, response_status = self._request(
            "subscription_create",
            "POST",
            "/preapproval",
            json=payload,
            extra_headers={"X-Idempotency-Key": idempotency_key},
        )
        subscription_id = normalize_resource_id(response.get("id"))
        status = str(response.get("status") or "").strip().lower()
        if not subscription_id or not status:
            raise MercadoPagoError(
                operation="subscription_create",
                endpoint="/preapproval",
                status=response_status,
                provider_code="invalid_response",
                provider_message="Mercado Pago não retornou id e status válidos.",
            )
        return AuthorizedSubscription(subscription_id, status)

    def create_payment(
        self,
        payload: dict[str, Any],
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        response, _status = self._request(
            "payment_create",
            "POST",
            "/v1/payments",
            json=payload,
            extra_headers={"X-Idempotency-Key": idempotency_key},
        )
        return response

    def get_payment(self, payment_id: str) -> dict[str, Any]:
        normalized_id = str(payment_id or "").strip()
        if not normalized_id.isdigit():
            raise MercadoPagoError(
                operation="payment_get",
                endpoint="/v1/payments/{id}",
                status=None,
                provider_code="invalid_resource_id",
                provider_message="ID de pagamento inválido.",
            )
        response, _status = self._request(
            "payment_get", "GET", f"/v1/payments/{normalized_id}"
        )
        return response

    def get_payment_methods(self) -> list[dict[str, Any]]:
        response, _status = self._request(
            "payment_methods_get",
            "GET",
            "/v1/payment_methods",
            expected_response_type=list,
        )
        if not all(isinstance(item, dict) for item in response):
            raise MercadoPagoError(
                operation="payment_methods_get",
                endpoint="/v1/payment_methods",
                status=None,
                provider_code="invalid_response",
                provider_message="Mercado Pago retornou meios de pagamento inválidos.",
            )
        return response

    def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        path = f"/preapproval/{require_resource_id(subscription_id)}"
        response, _status = self._request("subscription_get", "GET", path)
        return response

    def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        path = f"/preapproval/{require_resource_id(subscription_id)}"
        response, _status = self._request(
            "subscription_cancel", "PUT", path, json={"status": "cancelled"}
        )
        return response

    def get_authorized_payment(self, authorized_payment_id: str) -> dict[str, Any]:
        normalized_id = str(authorized_payment_id or "").strip()
        if not normalized_id.isdigit():
            raise MercadoPagoError(
                operation="authorized_payment_get",
                endpoint="/authorized_payments/{id}",
                status=None,
                provider_code="invalid_resource_id",
                provider_message="ID de fatura recorrente inválido.",
            )
        path = f"/authorized_payments/{normalized_id}"
        response, _status = self._request("authorized_payment_get", "GET", path)
        return response

    def search_authorized_payments(self, subscription_id: str) -> list[dict[str, Any]]:
        normalized_id = require_resource_id(subscription_id)
        response, response_status = self._request(
            "authorized_payment_search",
            "GET",
            "/authorized_payments/search",
            params={"preapproval_id": normalized_id},
        )
        results = response.get("results")
        if not isinstance(results, list) or not all(
            isinstance(item, dict) for item in results
        ):
            raise MercadoPagoError(
                operation="authorized_payment_search",
                endpoint="/authorized_payments/search",
                status=response_status,
                provider_code="invalid_response",
                provider_message="Mercado Pago retornou uma lista de faturas invÃ¡lida.",
            )
        return results

    def _request(
        self,
        operation: str,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
        expected_response_type: type = dict,
    ) -> tuple[Any, int]:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)
        try:
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                json=json,
                params=params,
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise MercadoPagoError(
                operation=operation,
                endpoint=path,
                status=None,
                provider_code="timeout",
                provider_message="Tempo limite ao acessar o Mercado Pago.",
            ) from exc
        except requests.RequestException as exc:
            raise MercadoPagoError(
                operation=operation,
                endpoint=path,
                status=None,
                provider_code="network_error",
                provider_message="Falha de rede ao acessar o Mercado Pago.",
            ) from exc

        data = _response_json(response)
        if not response.ok:
            provider_code, provider_message = _provider_error(data)
            raise MercadoPagoError(
                operation=operation,
                endpoint=path,
                status=response.status_code,
                provider_code=provider_code,
                provider_message=provider_message,
            )
        if not isinstance(data, expected_response_type):
            raise MercadoPagoError(
                operation=operation,
                endpoint=path,
                status=response.status_code,
                provider_code="invalid_response",
                provider_message="Mercado Pago retornou uma resposta JSON inválida.",
            )
        return data, response.status_code


def _response_json(response: requests.Response) -> object:
    try:
        return response.json()
    except ValueError:
        return None


def _provider_error(data: object) -> tuple[str, str]:
    if not isinstance(data, dict):
        return "invalid_response", "Mercado Pago retornou erro sem JSON válido."

    cause = data.get("cause")
    first_cause = cause[0] if isinstance(cause, list) and cause else None
    first_cause = first_cause if isinstance(first_cause, dict) else {}
    code = data.get("error") or first_cause.get("code") or data.get("status")
    message = data.get("message") or first_cause.get("description")
    return str(code or "unknown"), str(
        message or "Erro não detalhado pelo Mercado Pago."
    )


def _safe_log_value(value: object, fallback: str) -> str:
    normalized = " ".join(str(value or "").split())[:300]
    return normalized or fallback


def normalize_resource_id(value: object) -> str:
    resource_id = str(value or "").strip()
    return resource_id if re.fullmatch(r"[A-Za-z0-9-]+", resource_id) else ""


def require_resource_id(value: object) -> str:
    resource_id = normalize_resource_id(value)
    if not resource_id:
        raise MercadoPagoError(
            operation="resource_validate",
            endpoint="local",
            status=None,
            provider_code="invalid_resource_id",
            provider_message="ID de assinatura inválido.",
        )
    return resource_id


def is_mercado_pago_checkout_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    hostname = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (
        hostname in {"mercadopago.com", "mercadopago.com.br"}
        or hostname.endswith((".mercadopago.com", ".mercadopago.com.br"))
    )
