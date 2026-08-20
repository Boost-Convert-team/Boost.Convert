import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from flask import Flask
from flask_login import LoginManager

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = BACKEND_ROOT.parent / "frontend"
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.main.checkout_routes import payments_bp
from Blueprints.services.payments.mercado_pago_gateway import MercadoPagoRequestError
from Blueprints.services.payments.subscription_service import (
    CheckoutValidationError,
    cancel_user_subscription,
    create_pro_subscription,
    reconcile_subscription,
)
from extensions import db
from models import Subscription, Usuario
from security import CSRF_HEADER_NAME, CSRF_SESSION_KEY, init_security


class PaymentCheckoutTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(
            __name__,
            template_folder=str(FRONTEND_ROOT / "templates"),
            static_folder=str(FRONTEND_ROOT / "static"),
        )
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="test-secret-key-with-at-least-32-characters",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            MERCADOPAGO_PUBLIC_KEY="APP_USR-public-key",
            MERCADOPAGO_ACCESS_TOKEN="private-token",
            MERCADOPAGO_WEBHOOK_URL="https://boostconvert.com.br/webhooks/mercado-pago",
            MERCADOPAGO_WEBHOOK_SECRET="webhook-secret",
            PRO_PLAN_PRICE="25.90",
            BASE_URL="https://boostconvert.com.br",
            CSRF_ENABLED=True,
            RATE_LIMIT_ENABLED=False,
            FORCE_HTTPS=False,
        )
        db.init_app(self.app)
        login_manager = LoginManager(self.app)

        @login_manager.user_loader
        def load_user(user_id):
            return db.session.get(Usuario, int(user_id))

        init_security(self.app)
        self.app.register_blueprint(payments_bp)
        with self.app.app_context():
            db.create_all()
            user = Usuario(email="buyer@example.com", nome="Buyer")
            other = Usuario(email="other@example.com", nome="Other")
            db.session.add_all([user, other])
            db.session.commit()
            self.user_id = user.id
            self.other_user_id = other.id
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_create_pro_uses_internal_plan_and_authenticated_user(self):
        with self.app.app_context():
            user = db.session.get(Usuario, self.user_id)
            key = str(uuid4())
            gateway = self.gateway()
            subscription = create_pro_subscription(
                user,
                {
                    "token": "temporary-card-token",
                    "transaction_amount": 0.01,
                    "currency_id": "USD",
                    "user_id": self.other_user_id,
                    "installments": 12,
                },
                key,
                "https://boostconvert.com.br/pagamento/retorno",
                gateway=gateway,
            )
            payload, sent_key = gateway.create_subscription.call_args.args
            self.assertEqual(sent_key, key)
            self.assertEqual(subscription.user_id, self.user_id)
            self.assertEqual(payload["payer_email"], "buyer@example.com")
            self.assertEqual(payload["card_token_id"], "temporary-card-token")
            self.assertEqual(
                payload["external_reference"], subscription.external_reference
            )
            self.assertEqual(payload["reason"], "BoostConvert PRO")
            self.assertEqual(payload["status"], "authorized")
            self.assertEqual(
                payload["auto_recurring"],
                {
                    "frequency": 1,
                    "frequency_type": "months",
                    "transaction_amount": 25.9,
                    "currency_id": "BRL",
                },
            )
            self.assertNotIn("temporary-card-token", str(subscription.__dict__))

    def test_same_attempt_creates_only_one_provider_subscription(self):
        with self.app.app_context():
            user = db.session.get(Usuario, self.user_id)
            key = str(uuid4())
            gateway = self.gateway()
            first = create_pro_subscription(
                user,
                {"token": "token-1"},
                key,
                "https://example.com/return",
                gateway=gateway,
            )
            second = create_pro_subscription(
                user,
                {"token": "token-2"},
                key,
                "https://example.com/return",
                gateway=gateway,
            )
            self.assertEqual(first.id, second.id)
            self.assertEqual(Subscription.query.count(), 1)
            gateway.create_subscription.assert_called_once()

    def test_rejected_card_attempt_does_not_block_a_new_attempt(self):
        with self.app.app_context():
            user = db.session.get(Usuario, self.user_id)
            rejected_gateway = Mock()
            rejected_gateway.create_subscription.side_effect = MercadoPagoRequestError(
                "subscription_create", 422, "bad_card_token"
            )
            with self.assertRaises(MercadoPagoRequestError):
                create_pro_subscription(
                    user,
                    {"token": "rejected-token"},
                    str(uuid4()),
                    "https://example.com/return",
                    gateway=rejected_gateway,
                )
            self.assertEqual(Subscription.query.one().status, "error")

            accepted_gateway = self.gateway()
            created = create_pro_subscription(
                user,
                {"token": "new-token"},
                str(uuid4()),
                "https://example.com/return",
                gateway=accepted_gateway,
            )
            self.assertEqual(created.provider_subscription_id, "sub-123")

    def test_idempotency_key_cannot_be_reused_by_another_user(self):
        with self.app.app_context():
            first_user = db.session.get(Usuario, self.user_id)
            second_user = db.session.get(Usuario, self.other_user_id)
            key = str(uuid4())
            gateway = self.gateway()
            create_pro_subscription(
                first_user,
                {"token": "token-1"},
                key,
                "https://example.com/return",
                gateway=gateway,
            )
            with self.assertRaises(CheckoutValidationError):
                create_pro_subscription(
                    second_user,
                    {"token": "token-2"},
                    key,
                    "https://example.com/return",
                    gateway=gateway,
                )
            gateway.create_subscription.assert_called_once()

    def test_cancel_and_reconcile_use_subscription_sdk_boundary(self):
        with self.app.app_context():
            user = db.session.get(Usuario, self.user_id)
            key = str(uuid4())
            gateway = self.gateway()
            subscription = create_pro_subscription(
                user,
                {"token": "token"},
                key,
                "https://example.com/return",
                gateway=gateway,
            )
            gateway.get_subscription.return_value = self.provider_subscription(
                subscription, "authorized"
            )
            gateway.search_invoices.return_value = []
            reconcile_subscription(subscription, gateway=gateway)
            gateway.get_subscription.assert_called_once_with("sub-123")
            gateway.search_invoices.assert_called_once_with("sub-123")

            gateway.cancel_subscription.return_value = self.provider_subscription(
                subscription, "canceled"
            )
            canceled = cancel_user_subscription(user, gateway=gateway)
            self.assertEqual(canceled.status, "canceled")
            gateway.cancel_subscription.assert_called_once_with("sub-123")

    def test_checkout_endpoint_requires_login_and_csrf(self):
        response = self.client.post(
            "/api/payments/checkout",
            json={"token": "token"},
            headers={**self.csrf_headers(), "X-Idempotency-Key": str(uuid4())},
        )
        self.assertEqual(response.status_code, 401)
        self.login()
        response = self.client.post(
            "/api/payments/checkout",
            json={"token": "token"},
            headers={"X-Idempotency-Key": str(uuid4())},
        )
        self.assertEqual(response.status_code, 400)

    def test_checkout_route_never_trusts_browser_user_or_amount(self):
        self.login()
        key = str(uuid4())
        with patch(
            "Blueprints.services.payments.subscription_service.MercadoPagoGateway"
        ) as gateway_class:
            gateway_class.return_value.create_subscription.return_value = {
                "id": "sub-route",
                "status": "authorized",
            }
            response = self.client.post(
                "/api/payments/checkout",
                json={
                    "token": "temporary",
                    "transaction_amount": 0.01,
                    "user_id": self.other_user_id,
                },
                headers={**self.csrf_headers(), "X-Idempotency-Key": key},
            )
        self.assertEqual(response.status_code, 201)
        payload = gateway_class.return_value.create_subscription.call_args.args[0]
        self.assertNotIn("transaction_amount", payload)
        self.assertEqual(payload["auto_recurring"]["transaction_amount"], 25.9)
        with self.app.app_context():
            self.assertEqual(Subscription.query.one().user_id, self.user_id)

    def test_frontend_uses_card_brick_and_one_installment(self):
        template = (FRONTEND_ROOT / "templates" / "checkout_card.html").read_text(
            encoding="utf-8"
        )
        script = (FRONTEND_ROOT / "static" / "js" / "payments.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("sdk.mercadopago.com/js/v2", template)
        self.assertIn('bricksBuilder.create("cardPayment"', script)
        self.assertIn("maxInstallments: 1", script)
        self.assertIn('return { token: String(formData?.token || "") }', script)
        self.assertNotIn("MERCADOPAGO_ACCESS_TOKEN", template + script)

    def gateway(self):
        gateway = Mock()
        gateway.create_subscription.return_value = {
            "id": "sub-123",
            "status": "authorized",
        }
        return gateway

    @staticmethod
    def provider_subscription(subscription, status):
        now = datetime.now(timezone.utc)
        return {
            "id": subscription.provider_subscription_id,
            "external_reference": subscription.external_reference,
            "status": status,
            "auto_recurring": {
                "frequency": 1,
                "frequency_type": "months",
                "transaction_amount": "25.90",
                "currency_id": "BRL",
            },
            "date_created": now.isoformat(),
            "next_payment_date": (now + timedelta(days=30)).isoformat(),
        }

    def login(self):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user_id)
            session["_fresh"] = True

    def csrf_headers(self):
        token = "test-csrf-token-with-enough-length-123"
        with self.client.session_transaction() as session:
            session[CSRF_SESSION_KEY] = token
        return {CSRF_HEADER_NAME: token, "Accept": "application/json"}


if __name__ == "__main__":
    unittest.main()
