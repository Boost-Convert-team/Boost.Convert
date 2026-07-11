import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.subscription.mercado_pago_payments_service import (
    create_one_time_checkout_preference,
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
            MERCADO_PAGO_PLAN_PRICE="19.90",
            BASE_URL="https://boostconvert.com.br",
        )
        db.init_app(self.app)
        with self.app.app_context():
            db.create_all()

    def tearDown(self) -> None:
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_creating_pix_persists_qr_but_never_activates_pro(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/api/payment/pix", method="POST"):
            user = Usuario(email="pix-create@example.com", plano="free", status_assinatura="inactive")
            db.session.add(user)
            db.session.commit()
            provider_data = {
                "id": "pay_pix_pending",
                "external_reference": f"boost:user:{user.id}",
                "status": "approved",
                "payment_method_id": "pix",
                "payment_type_id": "bank_transfer",
                "transaction_amount": "19.90",
                "currency_id": "BRL",
                "point_of_interaction": {
                    "transaction_data": {
                        "qr_code": "000201-pix-copy-code",
                        "qr_code_base64": "cXItY29kZQ==",
                    }
                },
            }

            with patch(
                "Blueprints.services.subscription.mercado_pago_payments_service.mercado_pago_request",
                return_value=provider_data,
            ) as request_payment:
                result = create_pix_payment(user)

            payment = Payment.query.filter_by(provider_payment_id="pay_pix_pending").one()
            self.assertEqual((user.plano, user.status_assinatura), ("free", "inactive"))
            self.assertIsNone(payment.premium_expires_at)
            self.assertIsNone(payment.approved_at)
            self.assertEqual(payment.pix_qr_code, "000201-pix-copy-code")
            self.assertEqual(result["payment_id"], "pay_pix_pending")

            _method, path = request_payment.call_args.args[:2]
            kwargs = request_payment.call_args.kwargs
            self.assertEqual(path, "/v1/payments")
            self.assertEqual(kwargs["json_payload"]["payment_method_id"], "pix")
            self.assertEqual(kwargs["json_payload"]["transaction_amount"], 19.90)
            self.assertEqual(kwargs["json_payload"]["metadata"]["plan"], "BOOSTCONVERT_PRO")
            self.assertIn("X-Idempotency-Key", kwargs["extra_headers"])

    def test_existing_card_checkout_pro_preference_is_preserved(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/checkout/pro", method="POST"):
            user = Usuario(email="card@example.com", plano="free", status_assinatura="inactive")
            db.session.add(user)
            db.session.commit()
            with patch(
                "Blueprints.services.subscription.mercado_pago_payments_service.mercado_pago_request",
                return_value={
                    "id": "pref_card_123",
                    "init_point": "https://www.mercadopago.com.br/checkout/v1/redirect?pref_id=123",
                },
            ) as request_preference:
                result = create_one_time_checkout_preference(user)

            self.assertEqual(result["preference_id"], "pref_card_123")
            self.assertIn("mercadopago.com.br", result["checkout_url"])
            self.assertEqual(request_preference.call_args.args[:2], ("POST", "/checkout/preferences"))


if __name__ == "__main__":
    unittest.main()
