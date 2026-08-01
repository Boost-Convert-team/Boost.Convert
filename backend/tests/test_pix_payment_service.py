import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.subscription.mercado_pago_payments_service import (
    PayerValidationError,
    create_pix_payment,
)
from Blueprints.services.subscription.mercado_pago_service import (
    MercadoPagoConfigurationError,
)
from extensions import db
from models import Payment, Usuario


class PixPaymentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            MERCADO_PAGO_ACCESS_TOKEN="TEST-token",
            MERCADO_PAGO_PLAN_PRICE="19.90",
            MERCADO_PAGO_ENVIRONMENT="test",
            MERCADO_PAGO_COLLECTOR_ID="123456",
            BASE_URL="https://boostconvert.com.br",
        )
        db.init_app(self.app)
        with self.app.app_context():
            db.create_all()

    def tearDown(self) -> None:
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_pix_has_unique_attempt_reference_and_does_not_activate_on_create(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/api/payment/pix", method="POST"):
            user = self.create_user("pix-create@example.com")
            idempotency_key = "11111111-2222-4333-8444-555555555555"
            calls = []

            def provider_request(method, path, **kwargs):
                calls.append((method, path, kwargs))
                if path.startswith("/v1/payments/search?"):
                    return {"results": []}
                payload = kwargs["json_payload"]
                return self.provider_pix_data("pay_pix_pending", payload, status="approved")

            with patch(
                "Blueprints.services.subscription.mercado_pago_payments_service.mercado_pago_request",
                side_effect=provider_request,
            ):
                result = create_pix_payment(user, idempotency_key)
                repeated_result = create_pix_payment(user, idempotency_key)

            payment = Payment.query.filter_by(provider_payment_id="pay_pix_pending").one()
            self.assertEqual((user.plano, user.status_assinatura), ("free", "inactive"))
            self.assertIsNone(payment.premium_expires_at)
            self.assertIsNone(payment.approved_at)
            self.assertEqual(payment.attempt_id, result["attempt_id"])
            self.assertEqual(
                payment.external_reference,
                f"boost:payment:{payment.attempt_id}:user:{user.id}",
            )
            self.assertEqual(payment.pix_qr_code, "000201-pix-copy-code")
            self.assertEqual(repeated_result, result)
            self.assertEqual(len(calls), 2)
            post_call = calls[1]
            self.assertEqual(post_call[0:2], ("POST", "/v1/payments"))
            self.assertEqual(post_call[2]["json_payload"]["payment_method_id"], "pix")
            self.assertEqual(post_call[2]["json_payload"]["transaction_amount"], 19.90)
            self.assertEqual(
                post_call[2]["json_payload"]["payer"],
                {"email": "pix-create@example.com"},
            )
            self.assertEqual(
                post_call[2]["json_payload"]["notification_url"],
                "https://boostconvert.com.br/api/webhooks/mercadopago",
            )
            self.assertEqual(post_call[2]["json_payload"]["metadata"]["plan"], "pro")
            self.assertEqual(
                post_call[2]["json_payload"]["metadata"]["attempt_id"],
                payment.attempt_id,
            )
            self.assertEqual(
                post_call[2]["extra_headers"]["X-Idempotency-Key"],
                idempotency_key,
            )

    def test_two_pix_attempts_for_same_user_have_different_references(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/api/payment/pix", method="POST"):
            user = self.create_user("pix-race@example.com")
            counter = 0

            def provider_request(method, path, **kwargs):
                nonlocal counter
                if path.startswith("/v1/payments/search?"):
                    return {"results": []}
                counter += 1
                return self.provider_pix_data(
                    f"pay_pix_{counter}", kwargs["json_payload"], status="pending"
                )

            with patch(
                "Blueprints.services.subscription.mercado_pago_payments_service.mercado_pago_request",
                side_effect=provider_request,
            ):
                create_pix_payment(user, "11111111-2222-4333-8444-555555555555")
                create_pix_payment(user, "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee")

            payments = Payment.query.order_by(Payment.id).all()
            self.assertEqual(len(payments), 2)
            self.assertNotEqual(payments[0].attempt_id, payments[1].attempt_id)
            self.assertNotEqual(payments[0].external_reference, payments[1].external_reference)

    def test_recovery_search_prevents_second_provider_post(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/api/payment/pix", method="POST"):
            user = self.create_user("pix-recovery@example.com")
            attempt = Payment(
                user_id=user.id,
                provider="mercado_pago",
                idempotency_key="11111111-2222-4333-8444-555555555555",
                external_reference=(
                    f"boost:payment:11111111-2222-4333-8444-555555555555:user:{user.id}"
                ),
                plan="BOOSTCONVERT_PRO",
                payment_method="pix",
                status="creating",
                amount="19.90",
                currency="BRL",
            )
            db.session.add(attempt)
            db.session.commit()
            recovered = self.provider_pix_data(
                "pay_recovered",
                {
                    "external_reference": attempt.external_reference,
                    "metadata": {
                        "user_id": user.id,
                        "plan": "BOOSTCONVERT_PRO",
                        "attempt_id": attempt.attempt_id,
                    },
                },
                status="pending",
            )

            with patch(
                "Blueprints.services.subscription.mercado_pago_payments_service.mercado_pago_request",
                return_value={"results": [recovered]},
            ) as request_payment:
                result = create_pix_payment(user, attempt.idempotency_key)

            self.assertEqual(result["payment_id"], "pay_recovered")
            self.assertEqual(request_payment.call_count, 1)
            self.assertEqual(request_payment.call_args.args[0], "GET")

    def test_missing_access_token_fails_before_database_or_provider(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/api/payment/pix", method="POST"):
            user = self.create_user("pix-missing-token@example.com")
            self.app.config["MERCADO_PAGO_ACCESS_TOKEN"] = None
            with patch(
                "Blueprints.services.subscription.mercado_pago_payments_service.mercado_pago_request"
            ) as provider_request, self.assertRaises(MercadoPagoConfigurationError) as raised:
                create_pix_payment(user, "11111111-2222-4333-8444-555555555555")
            self.assertEqual(raised.exception.code, "payment_access_token_missing")
            provider_request.assert_not_called()
            self.assertEqual(Payment.query.count(), 0)

    def test_missing_environment_uses_test_only_fallback(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/api/payment/pix", method="POST"):
            user = self.create_user("pix-test-fallback@example.com")
            self.app.config.update(
                MERCADO_PAGO_ENVIRONMENT="",
                MERCADO_PAGO_PUBLIC_KEY="TEST-public-key",
            )

            def provider_request(method, path, **kwargs):
                if path.startswith("/v1/payments/search?"):
                    return {"results": []}
                return self.provider_pix_data(
                    "pay_test_fallback", kwargs["json_payload"], status="pending"
                )

            with patch(
                "Blueprints.services.subscription.mercado_pago_payments_service.mercado_pago_request",
                side_effect=provider_request,
            ):
                result = create_pix_payment(
                    user, "11111111-2222-4333-8444-555555555555"
                )
            self.assertEqual(result["payment_id"], "pay_test_fallback")
            self.assertTrue(result["qr_code"])
            self.assertTrue(result["qr_code_base64"])

    def test_invalid_payer_email_is_rejected_before_provider(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/api/payment/pix", method="POST"):
            user = self.create_user("invalid-email")
            with patch(
                "Blueprints.services.subscription.mercado_pago_payments_service.mercado_pago_request"
            ) as provider_request, self.assertRaises(PayerValidationError):
                create_pix_payment(user, "11111111-2222-4333-8444-555555555555")
            provider_request.assert_not_called()

    def create_user(self, email: str) -> Usuario:
        user = Usuario(email=email, plano="free", status_assinatura="inactive")
        db.session.add(user)
        db.session.commit()
        return user

    def provider_pix_data(
        self,
        payment_id: str,
        request_payload: dict,
        *,
        status: str,
    ) -> dict:
        metadata = dict(request_payload.get("metadata") or {})
        return {
            "id": payment_id,
            "external_reference": request_payload["external_reference"],
            "status": status,
            "payment_method_id": "pix",
            "payment_type_id": "bank_transfer",
            "transaction_amount": "19.90",
            "currency_id": "BRL",
            "collector_id": 123456,
            "live_mode": False,
            "date_created": "2026-07-31T10:15:00Z",
            "metadata": metadata,
            "point_of_interaction": {
                "transaction_data": {
                    "qr_code": "000201-pix-copy-code",
                    "qr_code_base64": "cXItY29kZQ==",
                    "ticket_url": f"https://www.mercadopago.com.br/payments/{payment_id}/ticket",
                }
            },
        }


if __name__ == "__main__":
    unittest.main()
