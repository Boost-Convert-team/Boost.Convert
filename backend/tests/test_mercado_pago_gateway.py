import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from flask import Flask
from mercadopago.errors import MPBadRequestError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.payments.mercado_pago_gateway import (
    MercadoPagoConfigurationError,
    MercadoPagoGateway,
    MercadoPagoRequestError,
    checkout_error_status,
)


class MercadoPagoGatewayTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            MERCADOPAGO_ACCESS_TOKEN="private-test-token",
            MERCADOPAGO_REQUEST_TIMEOUT_SECONDS=7.0,
        )

    def test_builds_official_sdk(self):
        with (
            self.app.app_context(),
            patch(
                "Blueprints.services.payments.mercado_pago_gateway.mercadopago.SDK"
            ) as sdk_class,
        ):
            MercadoPagoGateway()
            sdk_class.assert_called_once()
            self.assertEqual(sdk_class.call_args.args[0], "private-test-token")
            options = sdk_class.call_args.kwargs["request_options"]
            self.assertEqual(options.connection_timeout, 7.0)

    def test_missing_access_token_is_configuration_error(self):
        self.app.config["MERCADOPAGO_ACCESS_TOKEN"] = ""
        with self.app.app_context(), self.assertRaises(MercadoPagoConfigurationError):
            MercadoPagoGateway()

    def test_create_uses_preapproval_and_request_options(self):
        sdk = Mock()
        sdk.preapproval.return_value.create.return_value = {
            "status": 201,
            "response": {"id": "sub-1", "status": "authorized"},
        }
        result = MercadoPagoGateway(sdk).create_subscription(
            {"reason": "BoostConvert PRO"}, "idem-key"
        )
        self.assertEqual(result["id"], "sub-1")
        args = sdk.preapproval.return_value.create.call_args.args
        self.assertEqual(args[0]["reason"], "BoostConvert PRO")
        self.assertEqual(args[1].custom_headers, {"x-idempotency-key": "idem-key"})
        sdk.payment.assert_not_called()

    def test_get_cancel_and_invoice_use_official_resources(self):
        sdk = Mock()
        sdk.preapproval.return_value.get.return_value = {
            "status": 200,
            "response": {"id": "sub-1"},
        }
        sdk.preapproval.return_value.update.return_value = {
            "status": 200,
            "response": {"id": "sub-1", "status": "canceled"},
        }
        sdk.invoice.return_value.get.return_value = {
            "status": 200,
            "response": {"id": 501},
        }
        gateway = MercadoPagoGateway(sdk)
        gateway.get_subscription("sub-1")
        gateway.cancel_subscription("sub-1")
        gateway.get_invoice("501")
        sdk.preapproval.return_value.get.assert_called_once_with("sub-1")
        sdk.preapproval.return_value.update.assert_called_once_with(
            "sub-1", {"status": "canceled"}
        )
        sdk.invoice.return_value.get.assert_called_once_with("501")

    def test_non_success_response_is_mapped(self):
        sdk = Mock()
        sdk.preapproval.return_value.create.return_value = {
            "status": 422,
            "response": {"error": "bad_card_token"},
        }
        with self.assertRaises(MercadoPagoRequestError) as raised:
            MercadoPagoGateway(sdk).create_subscription({}, "idem")
        self.assertEqual(raised.exception.status, 422)
        self.assertEqual(raised.exception.provider_code, "bad_card_token")

    def test_bad_request_preserves_safe_official_sdk_details(self):
        sdk = Mock()
        sdk_error = MPBadRequestError(
            400,
            {
                "message": "The recurring payment data is invalid",
                "error": "bad_request",
                "cause": [
                    {
                        "code": "invalid_frequency",
                        "description": "Frequency must be greater than zero",
                        "ignored_provider_field": "must-not-be-copied",
                    }
                ],
            },
        )
        sdk_error.request_id = "request-123"
        sdk.preapproval.return_value.create.side_effect = sdk_error

        with self.assertRaises(MercadoPagoRequestError) as raised:
            MercadoPagoGateway(sdk).create_subscription({}, "idem")

        error = raised.exception
        self.assertEqual(error.status, 400)
        self.assertEqual(error.provider_error, "bad_request")
        self.assertEqual(
            error.provider_message, "The recurring payment data is invalid"
        )
        self.assertEqual(
            error.provider_causes,
            (
                {
                    "code": "invalid_frequency",
                    "description": "Frequency must be greater than zero",
                },
            ),
        )
        self.assertEqual(error.request_id, "request-123")

    def test_bad_request_uses_cause_code_when_error_field_is_empty(self):
        sdk = Mock()
        sdk.preapproval.return_value.create.side_effect = MPBadRequestError(
            400,
            {
                "message": "Invalid request",
                "cause": [{"code": "payer_email_invalid"}],
            },
        )
        with self.assertRaises(MercadoPagoRequestError) as raised:
            MercadoPagoGateway(sdk).create_subscription({}, "idem")
        self.assertEqual(raised.exception.provider_error, "payer_email_invalid")
        self.assertNotEqual(raised.exception.provider_error, "sdk_error")

    def test_http_status_mapping(self):
        cases = {
            400: 422,
            401: 503,
            403: 503,
            404: 503,
            409: 409,
            422: 422,
            429: 503,
            500: 502,
            502: 502,
            503: 502,
            None: 503,
        }
        for provider_status, expected in cases.items():
            with self.subTest(provider_status=provider_status):
                error = MercadoPagoRequestError(
                    "subscription_create", provider_status, "test"
                )
                self.assertEqual(checkout_error_status(error), expected)

    def test_timeout_is_mapped_without_exposing_transport(self):
        sdk = Mock()
        sdk.preapproval.return_value.create.side_effect = requests.Timeout()
        with self.assertRaises(MercadoPagoRequestError) as raised:
            MercadoPagoGateway(sdk).create_subscription({}, "idem")
        self.assertIsNone(raised.exception.status)
        self.assertEqual(raised.exception.provider_code, "timeout")


if __name__ == "__main__":
    unittest.main()
