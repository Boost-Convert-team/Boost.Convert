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
    def test_payment_creation_uses_v1_payments_and_idempotency(self, request_call):
        request_call.return_value = self.response(
            201,
            {
                "id": 123456,
                "status": "pending",
            },
        )
        result = self.client.create_payment(
            {"token": "not-logged"}, idempotency_key="payment-attempt-123"
        )
        self.assertEqual(result["id"], 123456)
        self.assertEqual(result["status"], "pending")
        call = request_call.call_args
        self.assertEqual(
            call.args[:2], ("POST", "https://api.mercadopago.com/v1/payments")
        )
        self.assertEqual(
            call.kwargs["headers"]["X-Idempotency-Key"], "payment-attempt-123"
        )
        self.assertEqual(call.kwargs["timeout"], 7)

    @patch("Blueprints.services.payments.mercado_pago_client.requests.request")
    def test_authorized_subscription_uses_preapproval_without_init_point(
        self, request_call
    ):
        request_call.return_value = self.response(
            201,
            {
                "id": "sub-123",
                "status": "authorized",
            },
        )

        result = self.client.create_authorized_subscription(
            {"card_token_id": "not-logged", "status": "authorized"},
            idempotency_key="subscription-attempt-123",
        )

        self.assertEqual(result.subscription_id, "sub-123")
        self.assertEqual(result.status, "authorized")
        call = request_call.call_args
        self.assertEqual(
            call.args[:2], ("POST", "https://api.mercadopago.com/preapproval")
        )
        self.assertEqual(
            call.kwargs["headers"]["X-Idempotency-Key"],
            "subscription-attempt-123",
        )
        self.assertNotIn("init_point", request_call.return_value.json.return_value)

    @patch("Blueprints.services.payments.mercado_pago_client.requests.request")
    def test_authorized_subscription_requires_id_and_status(self, request_call):
        for response_data in ({"status": "authorized"}, {"id": "sub-123"}):
            with self.subTest(response_data=response_data):
                request_call.return_value = self.response(201, response_data)
                with self.assertRaises(MercadoPagoError) as raised:
                    self.client.create_authorized_subscription(
                        {"card_token_id": "not-logged"},
                        idempotency_key="subscription-attempt-123",
                    )
                self.assertEqual(raised.exception.provider_code, "invalid_response")

    @patch("Blueprints.services.payments.mercado_pago_client.requests.request")
    def test_authorized_payment_search_is_scoped_to_subscription(self, request_call):
        request_call.return_value = self.response(
            200,
            {"paging": {"total": 1}, "results": [{"id": 501}]},
        )

        results = self.client.search_authorized_payments("sub-123")

        self.assertEqual(results, [{"id": 501}])
        call = request_call.call_args
        self.assertEqual(
            call.args[:2],
            ("GET", "https://api.mercadopago.com/authorized_payments/search"),
        )
        self.assertEqual(call.kwargs["params"], {"preapproval_id": "sub-123"})

    @patch("Blueprints.services.payments.mercado_pago_client.requests.request")
    def test_payment_get_uses_official_resource(self, request_call):
        request_call.return_value = self.response(
            200, {"id": 123456, "status": "approved"}
        )
        result = self.client.get_payment("123456")
        self.assertEqual(result["status"], "approved")
        self.assertEqual(
            request_call.call_args.args[:2],
            ("GET", "https://api.mercadopago.com/v1/payments/123456"),
        )

    @patch("Blueprints.services.payments.mercado_pago_client.requests.request")
    def test_authorized_payment_search_rejects_malformed_results(self, request_call):
        request_call.return_value = self.response(200, {"results": {"id": 501}})

        with self.assertRaises(MercadoPagoError) as raised:
            self.client.search_authorized_payments("sub-123")

        self.assertEqual(raised.exception.provider_code, "invalid_response")

    @patch("Blueprints.services.payments.mercado_pago_client.requests.request")
    def test_subscription_cancel_uses_provider_supported_status(self, request_call):
        request_call.return_value = self.response(
            200,
            {
                "id": "sub-123",
                "external_reference": "boost:subscription:123",
                "status": "cancelled",
            },
        )

        result = self.client.cancel_subscription("sub-123")

        self.assertEqual(result["status"], "cancelled")
        call = request_call.call_args
        self.assertEqual(
            call.args[:2],
            ("PUT", "https://api.mercadopago.com/preapproval/sub-123"),
        )
        self.assertEqual(call.kwargs["json"], {"status": "cancelled"})

    @patch("Blueprints.services.payments.mercado_pago_client.requests.request")
    def test_provider_http_errors_keep_safe_diagnostics(self, request_call):
        for status in (400, 401, 403, 422, 500):
            with self.subTest(status=status):
                request_call.return_value = self.response(
                    status,
                    {
                        "error": f"provider_{status}",
                        "message": f"provider message {status}",
                    },
                )
                with self.assertRaises(MercadoPagoError) as raised:
                    self.client.create_payment(
                        {"token": "not-logged"}, idempotency_key="attempt"
                    )
                error = raised.exception
                self.assertEqual(error.status, status)
                self.assertEqual(error.operation, "payment_create")
                self.assertEqual(error.endpoint, "/v1/payments")
                self.assertEqual(error.provider_code, f"provider_{status}")
                self.assertNotIn("private-test-token", str(error))

    @patch("Blueprints.services.payments.mercado_pago_client.requests.request")
    def test_subscription_http_errors_keep_safe_diagnostics(self, request_call):
        for status in (400, 401, 403, 422, 500):
            with self.subTest(status=status):
                request_call.return_value = self.response(
                    status,
                    {
                        "error": f"provider_{status}",
                        "message": f"provider message {status}",
                    },
                )
                with self.assertRaises(MercadoPagoError) as raised:
                    self.client.create_authorized_subscription(
                        {"card_token_id": "not-logged"},
                        idempotency_key="attempt",
                    )
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
            self.client.create_payment(
                {"token": "not-logged"}, idempotency_key="attempt"
            )
        self.assertEqual(raised.exception.provider_code, "timeout")
        self.assertIsNone(raised.exception.status)

    @patch("Blueprints.services.payments.mercado_pago_client.requests.request")
    def test_payment_methods_reject_malformed_response(self, request_call):
        request_call.return_value = self.response(200, {"id": "visa"})
        with self.assertRaises(MercadoPagoError) as raised:
            self.client.get_payment_methods()
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
