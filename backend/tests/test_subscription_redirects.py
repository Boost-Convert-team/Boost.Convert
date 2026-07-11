import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import url_for


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from Blueprints.main.checkout_routes import (
    checkout,
    checkout_credit_subscription,
    checkout_pro,
    create_pix_payment as create_pix_payment_route,
)
from Blueprints.handlers.conversion_handlers import (
    handle_conversion_error,
    validate_uploaded_file_count,
)
from Blueprints.services.convertions_services.upload_flow.job_factory import (
    validate_single_file_upload,
)
from Blueprints.services.subscription.access_service import UpgradeRequiredError
from security import CSRF_FIELD_NAME, CSRF_SESSION_KEY, clear_rate_limit_state


class SubscriptionRedirectTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_rate_limit_state()
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def test_anonymous_checkout_redirects_to_login(self) -> None:
        response = self.client.post("/checkout/pro", data=self.csrf_data())

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

        choice_response = self.client.get("/checkout-pro")
        self.assertEqual(choice_response.status_code, 302)
        self.assertIn("/login", choice_response.headers["Location"])

    def test_checkout_get_redirects_to_planos(self) -> None:
        with self.app.test_request_context("/checkout"):
            checkout_response = checkout.__wrapped__()

        self.assertEqual(checkout_response.location, "/planos")

    def test_credit_subscription_returns_mercado_pago_checkout_url(self) -> None:
        mercado_pago_response = {
            "checkout_url": "https://www.mercadopago.com.br/subscriptions/checkout?preapproval_id=sub_123",
            "subscription_id": "sub_123",
            "status": "pending",
            "plan_name": "BoostConvert PRO",
        }
        with self.app.test_request_context("/checkout/credit-subscription", method="POST"):
            with patch(
                "Blueprints.main.checkout_routes.create_monthly_subscription",
                return_value=mercado_pago_response,
            ):
                checkout_response, status_code = checkout_credit_subscription.__wrapped__()

        self.assertEqual(status_code, 200)
        self.assertEqual(checkout_response.json["provider"], "mercado_pago")
        self.assertEqual(checkout_response.json["plan_name"], "BoostConvert PRO")
        self.assertEqual(checkout_response.json["checkout_url"], mercado_pago_response["checkout_url"])

    def test_credit_subscription_returns_json_error_when_mercado_pago_fails(self) -> None:
        from Blueprints.services.subscription.mercado_pago_service import MercadoPagoError

        with self.app.test_request_context("/checkout/credit-subscription", method="POST"):
            with patch(
                "Blueprints.main.checkout_routes.create_monthly_subscription",
                side_effect=MercadoPagoError("MERCADO_PAGO_ACCESS_TOKEN nao configurado."),
            ):
                checkout_response = checkout_credit_subscription.__wrapped__()

        response, status_code = checkout_response
        self.assertEqual(status_code, 502)
        self.assertFalse(response.json["ok"])

    def test_pro_checkout_returns_hosted_mercado_pago_checkout_url(self) -> None:
        mercado_pago_response = {
            "ok": True,
            "provider": "mercado_pago",
            "plan_name": "BoostConvert PRO",
            "checkout_url": "https://www.mercadopago.com.br/checkout/v1/redirect?pref_id=123",
            "preference_id": "pref_123",
            "status": "created",
        }
        with self.app.test_request_context("/checkout/pro", method="POST"):
            with patch(
                "Blueprints.main.checkout_routes.create_one_time_checkout_preference",
                return_value=mercado_pago_response,
            ):
                response, status_code = checkout_pro.__wrapped__()

        self.assertEqual(status_code, 200)
        self.assertEqual(response.json["plan_name"], "BoostConvert PRO")
        self.assertEqual(response.json["checkout_url"], mercado_pago_response["checkout_url"])
        with self.app.test_request_context():
            self.assertEqual(url_for("checkout.checkout_pro"), "/checkout/pro")

    def test_pix_api_returns_local_checkout_redirect(self) -> None:
        pix_response = {
            "ok": True,
            "payment_id": "pay_pix_123",
            "status": "pending",
            "qr_code": "000201-code",
            "qr_code_base64": "cXI=",
        }
        with self.app.test_request_context("/api/payment/pix", method="POST"):
            with patch(
                "Blueprints.main.checkout_routes.current_user",
                SimpleNamespace(id=42, email="pix@example.com"),
            ), patch(
                "Blueprints.main.checkout_routes.create_mercado_pago_pix_payment",
                return_value=pix_response,
            ):
                response, status_code = create_pix_payment_route.__wrapped__()

        self.assertEqual(status_code, 201)
        self.assertEqual(response.json["payment_id"], "pay_pix_123")
        self.assertEqual(response.json["redirect_url"], "/checkout-pix?payment_id=pay_pix_123")

    def test_legacy_pix_and_debit_routes_use_same_hosted_checkout(self) -> None:
        mercado_pago_response = {
            "ok": True,
            "provider": "mercado_pago",
            "plan_name": "BoostConvert PRO",
            "checkout_url": "https://www.mercadopago.com.br/checkout/v1/redirect?pref_id=123",
            "preference_id": "pref_123",
            "status": "created",
        }
        for path in ("/checkout/pix", "/checkout/debit"):
            with self.subTest(path=path):
                with self.app.test_request_context(path, method="POST"):
                    with patch(
                        "Blueprints.main.checkout_routes.create_one_time_checkout_preference",
                        return_value=mercado_pago_response,
                    ):
                        response, status_code = checkout_pro.__wrapped__()

                self.assertEqual(status_code, 200)
                self.assertEqual(response.json["checkout_url"], mercado_pago_response["checkout_url"])

    def test_planos_pro_button_opens_payment_choice(self) -> None:
        template = (BACKEND_ROOT.parent / "frontend" / "templates" / "planos.html").read_text()
        choice_template = (BACKEND_ROOT.parent / "frontend" / "templates" / "checkout_pro.html").read_text()

        self.assertIn("url_for('checkout.checkout_pro_choice')", template)
        self.assertIn("BoostConvert PRO", template)
        self.assertIn('data-pro-checkout-form', choice_template)
        self.assertIn("url_for('checkout.checkout_pro')", choice_template)
        self.assertIn('data-pix-payment-form', choice_template)
        self.assertIn("url_for('checkout.create_pix_payment')", choice_template)
        self.assertNotIn('href="https://pay.', template)

    def test_upgrade_required_redirects_to_planos(self) -> None:
        with self.app.test_request_context("/convert/pdf-to-docx", method="POST"):
            response = handle_conversion_error(
                UpgradeRequiredError("Voce atingiu o limite de 10 conversoes."),
                "Arquivo recusado: %s",
                "Erro ao criar jobs",
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/planos")

    def test_free_file_count_limit_requires_upgrade(self) -> None:
        with self.assertRaises(UpgradeRequiredError):
            validate_uploaded_file_count([object(), object(), object()], None)

    def test_free_upload_size_limit_requires_upgrade(self) -> None:
        file = FakeUploadFile(size=51 * 1024 * 1024)

        with self.assertRaises(UpgradeRequiredError):
            validate_single_file_upload(file, None, "pdf", "docx")

    def test_pro_upload_size_limit_keeps_validation_error(self) -> None:
        file = FakeUploadFile(size=301 * 1024 * 1024)

        with self.assertRaises(ValueError):
            validate_single_file_upload(file, FakeProUser(), "pdf", "docx")

    def csrf_data(self) -> dict[str, str]:
        token = "test-csrf-token-with-enough-length-123"
        with self.client.session_transaction() as session:
            session[CSRF_SESSION_KEY] = token
        return {CSRF_FIELD_NAME: token}


class FakeProUser:
    plano = "pro"
    status_assinatura = "active"


class FakeUploadFile:
    def __init__(self, size: int) -> None:
        self.stream = FakeSizedStream(size)


class FakeSizedStream:
    def __init__(self, size: int) -> None:
        self.size = size
        self.position = 0

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = 0) -> None:
        if whence == 2:
            self.position = self.size + offset
            return
        self.position = offset


if __name__ == "__main__":
    unittest.main()
