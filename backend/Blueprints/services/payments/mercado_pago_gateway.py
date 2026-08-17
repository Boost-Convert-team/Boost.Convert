import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests
from flask import current_app


class MercadoPagoConfigurationError(RuntimeError):
    pass


class MercadoPagoGatewayError(RuntimeError):
    pass


@dataclass(frozen=True)
class SubscriptionPlanResult:
    plan_id: str


@dataclass(frozen=True)
class SubscriptionCheckout:
    subscription_id: str
    checkout_url: str
    status: str


class MercadoPagoGateway:
    def __init__(self) -> None:
        self.access_token = str(
            current_app.config.get("MERCADOPAGO_ACCESS_TOKEN") or ""
        ).strip()
        if not self.access_token:
            raise MercadoPagoConfigurationError(
                "MERCADOPAGO_ACCESS_TOKEN não está configurado."
            )
        self.base_url = str(current_app.config["MERCADOPAGO_API_BASE_URL"]).rstrip(
            "/"
        )
        self.timeout = int(
            current_app.config.get("MERCADOPAGO_REQUEST_TIMEOUT_SECONDS", 10)
        )

    def create_subscription_plan(
        self, payload: dict[str, Any]
    ) -> SubscriptionPlanResult:
        response = self._request("POST", "/preapproval_plan", json=payload)
        plan_id = normalize_resource_id(response.get("id"))
        if not plan_id:
            raise MercadoPagoGatewayError(
                "O provedor não retornou um plano de assinatura válido."
            )
        return SubscriptionPlanResult(plan_id)

    def create_subscription(
        self, payload: dict[str, Any]
    ) -> SubscriptionCheckout:
        response = self._request("POST", "/preapproval", json=payload)
        subscription_id = normalize_resource_id(response.get("id"))
        checkout_url = str(response.get("init_point") or "").strip()
        status = str(response.get("status") or "pending").strip().lower()
        if not subscription_id or not is_mercado_pago_checkout_url(checkout_url):
            raise MercadoPagoGatewayError(
                "O provedor não retornou um checkout de assinatura válido."
            )
        return SubscriptionCheckout(subscription_id, checkout_url, status)

    def get_subscription_plan(self, plan_id: str) -> dict[str, Any]:
        return self._request(
            "GET", f"/preapproval_plan/{require_resource_id(plan_id)}"
        )

    def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        return self._request(
            "GET", f"/preapproval/{require_resource_id(subscription_id)}"
        )

    def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        return self._request(
            "PUT",
            f"/preapproval/{require_resource_id(subscription_id)}",
            json={"status": "cancelled"},
        )

    def get_authorized_payment(self, authorized_payment_id: str) -> dict[str, Any]:
        normalized_id = str(authorized_payment_id or "").strip()
        if not normalized_id.isdigit():
            raise MercadoPagoGatewayError("ID de fatura recorrente inválido.")
        return self._request("GET", f"/authorized_payments/{normalized_id}")

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                json=json,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise MercadoPagoGatewayError(
                "Não foi possível comunicar com o provedor de pagamento."
            ) from exc
        if not isinstance(data, dict):
            raise MercadoPagoGatewayError("Resposta inválida do provedor de pagamento.")
        return data


def normalize_resource_id(value: object) -> str:
    resource_id = str(value or "").strip()
    return resource_id if re.fullmatch(r"[A-Za-z0-9-]+", resource_id) else ""


def require_resource_id(value: object) -> str:
    resource_id = normalize_resource_id(value)
    if not resource_id:
        raise MercadoPagoGatewayError("ID de assinatura inválido.")
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
