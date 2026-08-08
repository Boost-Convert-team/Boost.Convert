import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from Blueprints.handlers.conversion_handlers import (
    handle_conversion_error,
    validate_uploaded_file_count,
)
from Blueprints.main.checkout_routes import (
    checkout,
    checkout_credit_subscription,
    checkout_pro_choice,
    legacy_checkout_disabled,
)
from Blueprints.main.checkout_routes import (
    create_card_payment as create_card_payment_route,
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

    def test_original_credit_subscription_route_is_preserved(self) -> None:
        subscription = {
            "plan_name": "BoostConvert PRO",
            "checkout_url": "https://www.mercadopago.com.br/subscriptions/checkout",
            "subscription_id": "sub_original",
            "status": "pending",
        }
        with (
            self.app.test_request_context(
                "/checkout/credit-subscription", method="POST"
            ),
            patch(
                "Blueprints.main.checkout_routes.current_user",
                SimpleNamespace(id=42, email="subscriber@example.com"),
            ),
            patch(
                "Blueprints.main.checkout_routes.create_monthly_subscription",
                return_value=subscription,
            ) as create_subscription,
        ):
            response, status_code = checkout_credit_subscription.__wrapped__()
        self.assertEqual(status_code, 200)
        self.assertEqual(response.json["subscription_id"], "sub_original")
        create_subscription.assert_called_once()

    def test_card_api_returns_local_status_redirect(self) -> None:
        mercado_pago_response = {
            "ok": True,
            "attempt_id": "11111111-2222-4333-8444-555555555555",
            "payment_id": "pay_card_123",
            "status": "approved",
            "approved": True,
        }
        with (
            self.app.test_request_context(
                "/api/payment/card",
                method="POST",
                json={
                    "token": "token",
                    "payment_method_id": "visa",
                    "issuer_id": "1",
                    "installments": 1,
                    "payer": {"email": "card@example.com"},
                },
                headers={"X-Idempotency-Key": "11111111-2222-4333-8444-555555555555"},
            ),
            patch(
                "Blueprints.main.checkout_routes.current_user",
                SimpleNamespace(id=42, email="card@example.com"),
            ),
            patch(
                "Blueprints.main.checkout_routes.create_mercado_pago_card_payment",
                return_value=mercado_pago_response,
            ),
        ):
            response, status_code = create_card_payment_route.__wrapped__()

        self.assertEqual(status_code, 201)
        self.assertEqual(response.json["payment_id"], "pay_card_123")
        self.assertIn(
            "/checkout-card/status?attempt_id=", response.json["redirect_url"]
        )

    def test_legacy_hosted_checkout_routes_are_disabled(self) -> None:
        for path in ("/checkout/debit", "/checkout/pro"):
            with self.subTest(path=path):
                with self.app.test_request_context(path, method="POST"):
                    _response, status_code = legacy_checkout_disabled.__wrapped__()
                self.assertEqual(status_code, 410)

    def test_planos_pro_button_opens_card_checkout(self) -> None:
        template = (
            BACKEND_ROOT.parent / "frontend" / "templates" / "planos.html"
        ).read_text(encoding="utf-8")
        choice_template = (
            BACKEND_ROOT.parent / "frontend" / "templates" / "checkout_pro.html"
        ).read_text(encoding="utf-8")

        self.assertIn("url_for('checkout.checkout_pro_choice')", template)
        self.assertIn("BoostConvert PRO", template)
        self.assertIn('id="cardPaymentBrick_container"', choice_template)
        self.assertIn("url_for('checkout.create_card_payment')", choice_template)
        self.assertIn("sdk.mercadopago.com/js/v2", choice_template)
        self.assertIn("Cartão de crédito", choice_template)
        self.assertIn('class="card-checkout-panel reveal"', choice_template)
        self.assertNotIn("sem renovação automática", choice_template)
        self.assertNotIn("30 dias", choice_template)
        self.assertNotIn('href="https://pay.', template)

    def test_removed_payment_routes_are_not_registered(self) -> None:
        paths = (
            "/api/payment/pix",
            "/api/payment/pix/<payment_id>/status",
            "/checkout-pix",
            "/checkout/pix",
        )
        registered_rules = {rule.rule for rule in self.app.url_map.iter_rules()}
        self.assertTrue(all(path not in registered_rules for path in paths))
        self.assertEqual(
            self.client.get("/checkout-pix?payment_id=missing").status_code, 404
        )
        self.assertEqual(
            self.client.get("/api/payment/pix/missing/status").status_code, 404
        )
        self.assertEqual(
            self.client.post("/api/payment/pix", data=self.csrf_data()).status_code,
            404,
        )

    def test_checkout_template_receives_only_the_public_mercado_pago_key(self) -> None:
        public_key = "TEST-public-key-visible-in-browser"
        access_token = "TEST-private-access-token-never-rendered"
        self.app.config.update(
            MERCADO_PAGO_PUBLIC_KEY=public_key,
            MERCADO_PAGO_ACCESS_TOKEN=access_token,
        )
        with (
            self.app.test_request_context("/checkout-pro"),
            patch(
                "Blueprints.main.checkout_routes.current_user",
                SimpleNamespace(id=42, email="payer@example.com"),
            ),
        ):
            rendered = checkout_pro_choice.__wrapped__()

        self.assertIn(f'data-public-key="{public_key}"', rendered)
        self.assertIn('id="cardPaymentBrick_container"', rendered)
        self.assertNotIn(access_token, rendered)

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
