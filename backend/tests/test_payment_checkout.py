import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from flask import Blueprint, Flask
from flask_login import LoginManager

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.main.checkout_routes import payments_bp
from Blueprints.services.payments.mercado_pago_gateway import (
    MercadoPagoGatewayError,
    SubscriptionCheckout,
    SubscriptionPlanResult,
)
from extensions import db
from models import PaymentPlanMapping, Subscription, Usuario
from security import CSRF_HEADER_NAME, CSRF_SESSION_KEY, init_security


class PaymentCheckoutTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="test-secret-key-with-at-least-32-characters",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            MERCADOPAGO_ACCESS_TOKEN="test-token",
            MERCADOPAGO_WEBHOOK_SECRET="test-webhook-secret",
            MERCADOPAGO_API_BASE_URL="https://api.mercadopago.com",
            MERCADOPAGO_REQUEST_TIMEOUT_SECONDS=10,
            PRO_PLAN_PRICE="25.90",
            PRO_PLAN_DURATION_DAYS=30,
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
        main = Blueprint("main", __name__)
        main.add_url_rule("/planos", "planos", lambda: "planos")
        home = Blueprint("home", __name__)
        home.add_url_rule("/conta", "conta", lambda: "conta")
        self.app.register_blueprint(main)
        self.app.register_blueprint(home)
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

    def test_checkout_requires_authentication(self):
        response = self.client.post(
            "/api/payments/checkout",
            json={"plan": "PRO"},
            headers=self.csrf_headers(),
        )
        self.assertEqual(response.status_code, 401)

    def test_invalid_plan_is_rejected(self):
        self.login()
        response = self.client.post(
            "/api/payments/checkout",
            json={"plan": "UNKNOWN"},
            headers={**self.csrf_headers(), "X-Idempotency-Key": str(uuid4())},
        )
        self.assertEqual(response.status_code, 400)

    @patch(
        "Blueprints.services.payments.payment_service.MercadoPagoGateway.create_subscription"
    )
    @patch(
        "Blueprints.services.payments.payment_service.MercadoPagoGateway.create_subscription_plan"
    )
    def test_checkout_uses_backend_monthly_plan_and_hosted_url(
        self, create_plan, create_subscription
    ):
        create_plan.return_value = SubscriptionPlanResult("plan-pro")
        create_subscription.return_value = SubscriptionCheckout(
            "sub-1",
            "https://www.mercadopago.com.br/subscriptions/checkout?preapproval_id=sub-1",
            "pending",
        )
        self.login()
        response = self.client.post(
            "/api/payments/checkout",
            json={"plan": "PRO", "price": 0.01},
            headers={**self.csrf_headers(), "X-Idempotency-Key": str(uuid4())},
        )
        self.assertEqual(response.status_code, 201)
        plan_payload = create_plan.call_args.args[0]
        self.assertEqual(plan_payload["auto_recurring"]["transaction_amount"], 25.90)
        self.assertEqual(plan_payload["auto_recurring"]["frequency_type"], "months")
        self.assertEqual(
            plan_payload["payment_methods_allowed"]["payment_types"],
            [{"id": "credit_card"}],
        )
        subscription_payload = create_subscription.call_args.args[0]
        self.assertEqual(subscription_payload["preapproval_plan_id"], "plan-pro")
        self.assertEqual(subscription_payload["payer_email"], "buyer@example.com")
        self.assertNotIn("card_token_id", subscription_payload)
        with self.app.app_context():
            subscription = Subscription.query.one()
            self.assertEqual(str(subscription.amount), "25.90")
            self.assertEqual(subscription.provider_subscription_id, "sub-1")
            self.assertEqual(PaymentPlanMapping.query.count(), 1)

    @patch(
        "Blueprints.services.payments.payment_service.MercadoPagoGateway.create_subscription"
    )
    @patch(
        "Blueprints.services.payments.payment_service.MercadoPagoGateway.create_subscription_plan"
    )
    def test_duplicate_key_reuses_subscription_and_plan_once(
        self, create_plan, create_subscription
    ):
        create_plan.return_value = SubscriptionPlanResult("plan-pro")
        create_subscription.return_value = SubscriptionCheckout(
            "sub-1", "https://www.mercadopago.com/subscriptions/checkout?id=sub-1", "pending"
        )
        self.login()
        key = str(uuid4())
        headers = {**self.csrf_headers(), "X-Idempotency-Key": key}
        first = self.client.post(
            "/api/payments/checkout", json={"plan": "PRO"}, headers=headers
        )
        second = self.client.post(
            "/api/payments/checkout", json={"plan": "PRO"}, headers=headers
        )
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(first.json["checkout_url"], second.json["checkout_url"])
        create_plan.assert_called_once()
        create_subscription.assert_called_once()

    @patch(
        "Blueprints.services.payments.payment_service.MercadoPagoGateway.create_subscription_plan",
        side_effect=MercadoPagoGatewayError("provider failed"),
    )
    def test_provider_error_is_safe(self, _create_plan):
        self.login()
        response = self.client.post(
            "/api/payments/checkout",
            json={"plan": "PRO"},
            headers={**self.csrf_headers(), "X-Idempotency-Key": str(uuid4())},
        )
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("provider failed", response.get_data(as_text=True))

    def test_unexpired_legacy_entitlement_is_preserved(self):
        with self.app.app_context():
            db.session.add(
                Subscription(
                    user_id=self.user_id,
                    provider="mercado_pago",
                    provider_subscription_id=f"checkout-pro:{self.user_id}",
                    external_reference=f"boost:payment:{uuid4()}",
                    plan="PRO",
                    status="active",
                    amount="25.90",
                    currency="BRL",
                    paid_through_at=datetime.now(timezone.utc) + timedelta(days=10),
                )
            )
            db.session.commit()
        self.login()
        response = self.client.post(
            "/api/payments/checkout",
            json={"plan": "PRO"},
            headers={**self.csrf_headers(), "X-Idempotency-Key": str(uuid4())},
        )
        self.assertEqual(response.status_code, 409)
        with self.app.app_context():
            self.assertEqual(Subscription.query.count(), 1)

    def test_cancel_uses_authenticated_users_subscription(self):
        with self.app.app_context():
            own = self.subscription(self.user_id, "sub-own")
            own_reference = own.external_reference
            self.subscription(self.other_user_id, "sub-other")
        self.login()
        with patch(
            "Blueprints.services.payments.payment_service.MercadoPagoGateway.cancel_subscription"
        ) as cancel:
            cancel.return_value = {
                "id": "sub-own",
                "external_reference": own_reference,
                "status": "cancelled",
            }
            response = self.client.post(
                "/api/subscriptions/cancel", headers=self.csrf_headers()
            )
        self.assertEqual(response.status_code, 200)
        cancel.assert_called_once_with("sub-own")
        with self.app.app_context():
            self.assertEqual(
                Subscription.query.filter_by(provider_subscription_id="sub-other").one().status,
                "active",
            )

    def subscription(self, user_id, provider_id):
        subscription = Subscription(
            user_id=user_id,
            provider="mercado_pago",
            provider_subscription_id=provider_id,
            provider_plan_id="plan-pro",
            external_reference=f"boost:subscription:{uuid4()}",
            plan="PRO",
            status="active",
            amount="25.90",
            currency="BRL",
        )
        db.session.add(subscription)
        db.session.commit()
        return subscription

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
