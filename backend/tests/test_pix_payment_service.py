import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.subscription.mercado_pago_payments_service import (
    create_pix_payment,
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
            MERCADO_PAGO_PUBLIC_KEY="TEST-public-key",
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

    def test_pending_pix_is_idempotent_and_keeps_checkout_data(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/api/payment/pix"):
            user = self.create_user("pix-pending@example.com")
            key = "11111111-2222-4333-8444-555555555555"
            calls = []

            def provider_request(method, path, **kwargs):
                calls.append((method, path, kwargs))
                if path.startswith("/v1/payments/search?"):
                    return {"results": []}
                return self.provider_pix_data(
                    "pay_pix_pending", kwargs["json_payload"], status="pending"
                )

            with patch(
                "Blueprints.services.subscription.mercado_pago_payments_service."
                "mercado_pago_request",
                side_effect=provider_request,
            ):
                result = create_pix_payment(user, key)
                repeated = create_pix_payment(user, key)

            payment = Payment.query.one()
            self.assertEqual(result, repeated)
            self.assertFalse(result["approved"])
            self.assertEqual(result["qr_code"], "000201-pix-copy-code")
            self.assertEqual(payment.payment_method, "pix")
            self.assertEqual(payment.payment_type_id, "bank_transfer")
            self.assertEqual(payment.provider_payment_method_id, "pix")
            self.assertEqual((user.plano, user.status_assinatura), ("free", "inactive"))
            self.assertEqual([call[0] for call in calls], ["GET", "POST"])
            self.assertEqual(calls[1][2]["extra_headers"]["X-Idempotency-Key"], key)
            self.assertEqual(calls[1][2]["json_payload"]["transaction_amount"], 19.90)

    def test_approved_pix_grants_pro_access_immediately(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/api/payment/pix"):
            user = self.create_user("pix-approved@example.com")

            def provider_request(method, path, **kwargs):
                if path.startswith("/v1/payments/search?"):
                    return {"results": []}
                return self.provider_pix_data(
                    "pay_pix_approved", kwargs["json_payload"], status="approved"
                )

            with patch(
                "Blueprints.services.subscription.mercado_pago_payments_service."
                "mercado_pago_request",
                side_effect=provider_request,
            ):
                result = create_pix_payment(
                    user, "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
                )

            payment = Payment.query.one()
            self.assertTrue(result["approved"])
            self.assertEqual((user.plano, user.status_assinatura), ("pro", "active"))
            self.assertIsNotNone(payment.approved_at)
            self.assertIsNotNone(payment.premium_expires_at)

    def create_user(self, email: str) -> Usuario:
        user = Usuario(email=email, plano="free", status_assinatura="inactive")
        db.session.add(user)
        db.session.commit()
        return user

    @staticmethod
    def provider_pix_data(
        payment_id: str, request_payload: dict, *, status: str
    ) -> dict:
        return {
            "id": payment_id,
            "external_reference": request_payload["external_reference"],
            "status": status,
            "status_detail": "accredited"
            if status == "approved"
            else "pending_waiting_payment",
            "payment_method_id": "pix",
            "payment_type_id": "bank_transfer",
            "transaction_amount": "19.90",
            "currency_id": "BRL",
            "collector_id": 123456,
            "live_mode": False,
            "date_created": "2026-07-31T10:15:00Z",
            "date_approved": "2026-07-31T10:16:00Z" if status == "approved" else None,
            "metadata": dict(request_payload["metadata"]),
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
