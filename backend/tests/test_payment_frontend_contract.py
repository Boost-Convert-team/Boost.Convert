import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class PaymentFrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.template = (
            PROJECT_ROOT / "frontend/templates/checkout_pro.html"
        ).read_text(encoding="utf-8")
        cls.javascript = (PROJECT_ROOT / "frontend/static/js/payments.js").read_text(
            encoding="utf-8"
        )
        cls.status_template = (
            PROJECT_ROOT / "frontend/templates/checkout_card_status.html"
        ).read_text(encoding="utf-8")
        cls.styles = (PROJECT_ROOT / "frontend/static/css/checkout.css").read_text(
            encoding="utf-8"
        )
        cls.app_javascript = (PROJECT_ROOT / "frontend/static/js/app.js").read_text(
            encoding="utf-8"
        )

    def test_checkout_offers_only_card_without_duplicating_card_brick(self) -> None:
        self.assertIn('aria-labelledby="card-checkout-title"', self.template)
        self.assertEqual(self.template.count('id="cardPaymentBrick_container"'), 1)
        self.assertEqual(self.template.count('class="card-checkout-panel reveal"'), 1)

    def test_removed_payment_method_has_no_frontend_artifacts(self) -> None:
        combined = f"{self.template}\n{self.javascript}\n{self.styles}".lower()
        self.assertNotIn("pix", combined)
        self.assertNotIn("qr_code", combined)

    def test_card_brick_is_created_once_with_credit_and_debit(self) -> None:
        self.assertEqual(self.javascript.count('bricksBuilder.create("cardPayment"'), 1)
        self.assertIn(
            'types: { included: ["credit_card", "debit_card"] }', self.javascript
        )
        self.assertIn("additionalData?.paymentTypeId", self.javascript)
        self.assertIn("cardBrickInitializing", self.javascript)
        self.assertIn("cardBrickController.unmount()", self.javascript)

    def test_payment_module_has_one_centralized_idempotent_initialization(self) -> None:
        self.assertNotIn(
            'document.addEventListener("DOMContentLoaded", initPayments)',
            self.javascript,
        )
        self.assertEqual(
            self.app_javascript.count("window.BoostPayments?.initPayments()"), 1
        )
        self.assertIn("if (cardSubmissionInFlight) return", self.javascript)
        self.assertIn(
            'page.dataset.paymentPollingInitialized === "true"', self.javascript
        )

    def test_card_sdk_loads_before_the_local_payment_initialization(self) -> None:
        self.assertIn("{% block extra_head %}", self.template)
        self.assertIn("https://sdk.mercadopago.com/js/v2", self.template)
        sdk_position = self.template.index("https://sdk.mercadopago.com/js/v2")
        content_position = self.template.index("{% block content %}")
        self.assertLess(sdk_position, content_position)

    def test_card_initialization_errors_are_visible_and_controlled(self) -> None:
        self.assertIn(
            'reportCardPaymentError("initialization", error)', self.javascript
        )
        self.assertIn('reportCardPaymentError("sdk", error)', self.javascript)
        self.assertIn(
            "Não foi possível iniciar o pagamento seguro por cartão.", self.javascript
        )
        self.assertIn(
            'catch (error) {\n            reportCardPaymentError("initialization", error)',
            self.javascript,
        )

    def test_duplicate_submission_guard_is_reset_after_error(self) -> None:
        self.assertIn("if (cardSubmissionInFlight) return", self.javascript)
        self.assertIn("cardSubmissionInFlight = true", self.javascript)
        self.assertIn("cardSubmissionInFlight = false", self.javascript)
        self.assertIn("finally", self.javascript)

    def test_only_public_key_is_exposed_to_frontend(self) -> None:
        combined = f"{self.template}\n{self.javascript}"
        self.assertIn("mercado_pago_public_key", self.template)
        self.assertNotIn("MERCADO_PAGO_ACCESS_TOKEN", combined)
        self.assertNotIn("MERCADO_PAGO_WEBHOOK_SECRET", combined)
        self.assertNotIn("Authorization: Bearer", combined)

    def test_card_payload_is_an_explicit_tokenized_whitelist(self) -> None:
        self.assertIn("token:", self.javascript)
        self.assertIn("payment_method_id:", self.javascript)
        self.assertIn("payment_type_id:", self.javascript)
        self.assertIn("issuer_id:", self.javascript)
        self.assertIn("installments:", self.javascript)
        for raw_field in ("card_number", "security_code", "expiration_date"):
            self.assertNotIn(raw_field, self.javascript)

    def test_status_page_uses_persisted_idempotency_key(self) -> None:
        self.assertIn("payment.idempotency_key", self.status_template)
        self.assertNotIn("payment.attempt_id", self.status_template)

    def test_checkout_is_responsive_without_horizontal_overflow(self) -> None:
        self.assertIn("width: min(720px, 100%);", self.styles)
        self.assertIn("overflow-x: clip;", self.styles)
        self.assertIn("@media (max-width: 760px)", self.styles)
        self.assertIn("@media (max-width: 480px)", self.styles)
        self.assertIn("min-width: 0;", self.styles)

    def test_original_commercial_terms_are_preserved(self) -> None:
        templates = "\n".join(
            (PROJECT_ROOT / path).read_text(encoding="utf-8")
            for path in (
                "frontend/templates/checkout_pro.html",
                "frontend/templates/checkout_card_status.html",
                "frontend/templates/home.html",
                "frontend/templates/planos.html",
            )
        )
        self.assertIn("{{ price }}", self.template)
        self.assertIn("Assinar BoostConvert PRO", templates)
        self.assertIn("/ m&ecirc;s", templates)
        for forbidden_copy in (
            "Compra única",
            "compra única",
            "Sem renovação",
            "sem renovação",
            "30 dias",
        ):
            self.assertNotIn(forbidden_copy, templates)


if __name__ == "__main__":
    unittest.main()
