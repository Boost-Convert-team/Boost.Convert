import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from flask import Flask

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.payments.mercado_pago_client import (
    MercadoPagoClient,
    MercadoPagoError,
)


class MercadoPagoClientTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            MERCADOPAGO_ACCESS_TOKEN="private-test-token",
            MERCADOPAGO_API_BASE_URL="https://api.mercadopago.com",
            MERCADOPAGO_REQUEST_TIMEOUT_SECONDS=7,
        )
        self.context = self.app.app_context()
        self.context.push()
        self.client = MercadoPagoClient()

    def tearDown(self):
        self.context.pop()

    @patch("Blueprints.services.payments.mercado_pago_client.requests.request")
    def test_checkout_created_with_official_init_point(self, request_call):
        request_call.return_value = self.response(
            201,
            {
                "id": "sub-123",
                "status": "pending",
                "init_point": "https://www.mercadopago.com.br/subscriptions/checkout?id=sub-123",
            },
        )
        result = self.client.create_subscription_checkout({"status": "pending"})
        self.assertEqual(result.subscription_id, "sub-123")
        self.assertEqual(result.status, "pending")
        call = request_call.call_args
        self.assertEqual(
            call.args[:2], ("POST", "https://api.mercadopago.com/preapproval")
        )
        self.assertEqual(call.kwargs["timeout"], 7)

    @patch("Blueprints.services.payments.mercado_pago_client.requests.request")
    def test_provider_http_errors_keep_safe_diagnostics(self, request_call):
        for status in (400, 401, 403, 500):
            with self.subTest(status=status):
                request_call.return_value = self.response(
                    status,
                    {
                        "error": f"provider_{status}",
                        "message": f"provider message {status}",
                    },
                )
                with self.assertRaises(MercadoPagoError) as raised:
                    self.client.create_subscription_checkout({"status": "pending"})
                error = raised.exception
                self.assertEqual(error.status, status)
                self.assertEqual(error.operation, "subscription_create")
                self.assertEqual(error.endpoint, "/preapproval")
                self.assertEqual(error.provider_code, f"provider_{status}")
                self.assertNotIn("private-test-token", str(error))

    @patch(
        "Blueprints.services.payments.mercado_pago_client.requests.request",
        side_effect=requests.Timeout,
    )
    def test_timeout_is_controlled(self, _request_call):
        with self.assertRaises(MercadoPagoError) as raised:
            self.client.create_subscription_checkout({"status": "pending"})
        self.assertEqual(raised.exception.provider_code, "timeout")
        self.assertIsNone(raised.exception.status)

    @patch("Blueprints.services.payments.mercado_pago_client.requests.request")
    def test_response_without_checkout_url_is_rejected(self, request_call):
        request_call.return_value = self.response(
            201, {"id": "sub-123", "status": "pending"}
        )
        with self.assertRaises(MercadoPagoError) as raised:
            self.client.create_subscription_checkout({"status": "pending"})
        self.assertEqual(raised.exception.provider_code, "invalid_response")

    @patch("Blueprints.services.payments.mercado_pago_client.requests.request")
    def test_non_json_error_is_controlled(self, request_call):
        response = Mock(status_code=500, ok=False)
        response.json.side_effect = ValueError
        request_call.return_value = response
        with self.assertRaises(MercadoPagoError) as raised:
            self.client.get_subscription("sub-123")
        self.assertEqual(raised.exception.provider_code, "invalid_response")

    @staticmethod
    def response(status, data):
        response = Mock(status_code=status, ok=200 <= status < 300)
        response.json.return_value = data
        return response


if __name__ == "__main__":
    unittest.main()
