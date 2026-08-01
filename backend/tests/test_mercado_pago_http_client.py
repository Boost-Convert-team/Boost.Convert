import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import requests
from flask import Flask


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.subscription.mercado_pago_service import (
    MercadoPagoHTTPError,
    MercadoPagoInvalidResponseError,
    MercadoPagoTimeoutError,
    mercado_pago_request,
)


class FakeResponse:
    def __init__(self, status_code, payload=None, *, headers=None, invalid_json=False):
        self.status_code = status_code
        self.payload = payload
        self.headers = headers or {}
        self.invalid_json = invalid_json

    def json(self):
        if self.invalid_json:
            raise ValueError("invalid json")
        return self.payload


class MercadoPagoHttpClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = Flask("mercado-pago-http")
        self.app.config["MERCADO_PAGO_ACCESS_TOKEN"] = "TEST-fake-token"

    def test_timeout_is_distinct_and_request_has_explicit_timeout(self) -> None:
        with self.app.app_context(), patch(
            "Blueprints.services.subscription.mercado_pago_service.requests.request",
            side_effect=requests.Timeout(),
        ) as request_call:
            with self.assertRaises(MercadoPagoTimeoutError):
                mercado_pago_request("POST", "/v1/payments", json_payload={"safe": True})
        self.assertEqual(request_call.call_args.kwargs["timeout"], 15)

    def test_provider_statuses_have_safe_explicit_mapping(self) -> None:
        expected = {
            400: 400,
            401: 502,
            403: 502,
            409: 409,
            422: 422,
            429: 503,
            500: 503,
            503: 503,
        }
        with self.app.app_context():
            for provider_status, public_status in expected.items():
                with self.subTest(provider_status=provider_status), patch(
                    "Blueprints.services.subscription.mercado_pago_service.requests.request",
                    return_value=FakeResponse(
                        provider_status,
                        {"error": "provider_error", "token": "must-not-log"},
                        headers={"Retry-After": "30"},
                    ),
                ), self.assertLogs(self.app.logger, level="WARNING") as logs:
                    with self.assertRaises(MercadoPagoHTTPError) as raised:
                        mercado_pago_request("POST", "/v1/payments", json_payload={})
                    self.assertEqual(raised.exception.public_status, public_status)
                    self.assertNotIn("must-not-log", " ".join(logs.output))
                    self.assertNotIn("token", " ".join(logs.output))
                    if provider_status == 429:
                        self.assertEqual(raised.exception.retry_after, "30")

    def test_invalid_json_or_unexpected_type_is_rejected(self) -> None:
        with self.app.app_context(), patch(
            "Blueprints.services.subscription.mercado_pago_service.requests.request",
            return_value=FakeResponse(200, invalid_json=True),
        ):
            with self.assertRaises(MercadoPagoInvalidResponseError):
                mercado_pago_request("GET", "/v1/payments/1")

    def test_provider_cause_and_correlation_are_sanitized(self) -> None:
        with self.app.app_context(), patch(
            "Blueprints.services.subscription.mercado_pago_service.requests.request",
            return_value=FakeResponse(
                422,
                {
                    "error": "bad_request",
                    "cause": [
                        {
                            "code": "2034",
                            "description": "Invalid users involved for buyer@example.com TEST-secret-value",
                        }
                    ],
                },
                headers={"x-request-id": "provider-correlation-123"},
            ),
        ), self.assertLogs(self.app.logger, level="WARNING") as logs:
            with self.assertRaises(MercadoPagoHTTPError) as raised:
                mercado_pago_request("POST", "/v1/payments", json_payload={})
        error = raised.exception
        self.assertEqual(error.provider_status, 422)
        self.assertEqual(error.provider_code, "bad_request")
        self.assertIn("2034", error.provider_cause)
        self.assertIn("[email]", error.provider_cause)
        self.assertIn("[credential]", error.provider_cause)
        self.assertEqual(error.correlation_id, "provider-correlation-123")
        combined_logs = " ".join(logs.output)
        self.assertNotIn("buyer@example.com", combined_logs)
        self.assertNotIn("TEST-secret-value", combined_logs)

        with self.app.app_context(), patch(
            "Blueprints.services.subscription.mercado_pago_service.requests.request",
            return_value=FakeResponse(200, ["unexpected"]),
        ):
            with self.assertRaises(MercadoPagoInvalidResponseError):
                mercado_pago_request("GET", "/v1/payments/1")


if __name__ == "__main__":
    unittest.main()
