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
from Blueprints.services.payments.mercado_pago_client import (
    MercadoPagoError,
    SubscriptionCheckout,
)
from extensions import db
from models import Subscription, Usuario
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
        response = self.post_checkout()
        self.assertEqual(response.status_code, 401)

    def test_invalid_plan_is_rejected(self):
        self.login()
        response = self.post_checkout(plan_id="UNKNOWN")
        self.assertEqual(response.status_code, 400)

    def test_missing_access_token_fails_before_external_request(self):
        self.login()
        self.app.config["MERCADOPAGO_ACCESS_TOKEN"] = ""
        with patch(
            "Blueprints.services.payments.mercado_pago_client.requests.request"
        ) as request_call:
            response = self.post_checkout()
        self.assertEqual(response.status_code, 503)
        request_call.assert_not_called()

    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.create_subscription_checkout"
    )
    def test_valid_checkout_uses_server_plan_and_hosted_pending_subscription(
        self, create_checkout
    ):
        create_checkout.return_value = SubscriptionCheckout(
            "sub-1",
            "https://www.mercadopago.com.br/subscriptions/checkout?preapproval_id=sub-1",
            "pending",
        )
        self.login()
        response = self.post_checkout(price=0.01, user_id=self.other_user_id)

        self.assertEqual(response.status_code, 201)
        payload = create_checkout.call_args.args[0]
        self.assertEqual(payload["payer_email"], "buyer@example.com")
        self.assertEqual(payload["auto_recurring"]["transaction_amount"], 25.90)
        self.assertEqual(payload["auto_recurring"]["currency_id"], "BRL")
        self.assertEqual(payload["auto_recurring"]["frequency"], 1)
        self.assertEqual(payload["auto_recurring"]["frequency_type"], "months")
        self.assertEqual(payload["status"], "pending")
        self.assertNotIn("preapproval_plan_id", payload)
        self.assertNotIn("card_token_id", payload)
        with self.app.app_context():
            subscription = Subscription.query.one()
            self.assertEqual(subscription.user_id, self.user_id)
            self.assertEqual(str(subscription.amount), "25.90")
            self.assertIsNone(subscription.provider_plan_id)
            self.assertEqual(subscription.provider_subscription_id, "sub-1")

    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.create_subscription_checkout"
    )
    def test_duplicate_key_reuses_checkout_once(self, create_checkout):
        create_checkout.return_value = SubscriptionCheckout(
            "sub-1",
            "https://www.mercadopago.com/subscriptions/checkout?id=sub-1",
            "pending",
        )
        self.login()
        key = str(uuid4())
        first = self.post_checkout(idempotency_key=key)
        second = self.post_checkout(idempotency_key=key)
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(first.json["checkout_url"], second.json["checkout_url"])
        create_checkout.assert_called_once()

    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.create_subscription_checkout",
        side_effect=MercadoPagoError(
            operation="subscription_create",
            endpoint="/preapproval",
            status=400,
            provider_code="bad_request",
            provider_message="card_token_id is required",
        ),
    )
    def test_provider_error_is_safe_for_frontend_and_detailed_in_log(self, _create):
        self.login()
        with self.assertLogs(self.app.logger.name, level="WARNING") as logs:
            response = self.post_checkout()
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("card_token_id is required", body)
        log_text = " ".join(logs.output)
        self.assertIn("status=400", log_text)
        self.assertIn("provider_code=bad_request", log_text)
        self.assertIn("user_id=1", log_text)
        self.assertIn("plan=PRO", log_text)
        self.assertNotIn("test-token", log_text)

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
        response = self.post_checkout()
        self.assertEqual(response.status_code, 409)

    def test_cancel_uses_authenticated_users_subscription(self):
        with self.app.app_context():
            own = self.subscription(self.user_id, "sub-own")
            own_reference = own.external_reference
            self.subscription(self.other_user_id, "sub-other")
        self.login()
        with patch(
            "Blueprints.services.payments.payment_service."
            "MercadoPagoClient.cancel_subscription"
        ) as cancel:
            cancel.return_value = {
                "id": "sub-own",
                "external_reference": own_reference,
                "status": "canceled",
            }
            response = self.client.post(
                "/api/subscriptions/cancel", headers=self.csrf_headers()
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "canceled")
        cancel.assert_called_once_with("sub-own")
        with self.app.app_context():
            self.assertEqual(
                Subscription.query.filter_by(provider_subscription_id="sub-other")
                .one()
                .status,
                "active",
            )

    def test_frontend_contains_no_mercado_pago_secret(self):
        frontend_root = BACKEND_ROOT.parent / "frontend"
        payment_script = (frontend_root / "static" / "js" / "payments.js").read_text(
            encoding="utf-8"
        )
        content = "\n".join(
            path.read_text(encoding="utf-8")
            for path in frontend_root.rglob("*")
            if path.is_file() and path.suffix in {".html", ".js", ".css"}
        )
        self.assertNotIn("MERCADOPAGO_ACCESS_TOKEN", content)
        self.assertNotIn("MERCADOPAGO_WEBHOOK_SECRET", content)
        self.assertNotIn("card_token_id", content)
        self.assertIn("window.location.assign(result.checkout_url)", payment_script)
        self.assertIn("JSON.stringify({ plan_id: payload.plan_id })", payment_script)

    def post_checkout(self, plan_id="PRO", idempotency_key=None, **extra):
        payload = {"plan_id": plan_id, **extra}
        return self.client.post(
            "/api/payments/checkout",
            json=payload,
            headers={
                **self.csrf_headers(),
                "X-Idempotency-Key": idempotency_key or str(uuid4()),
            },
        )

    def subscription(self, user_id, provider_id):
        subscription = Subscription(
            user_id=user_id,
            provider="mercado_pago",
            provider_subscription_id=provider_id,
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
