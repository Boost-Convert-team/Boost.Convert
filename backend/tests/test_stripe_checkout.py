import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Blueprint, Flask
from flask_login import LoginManager

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.main.checkout_routes import checkout_bp
from Blueprints.services.subscription.stripe_checkout_service import (
    StripeCheckoutError,
    StripeConfigurationError,
    create_subscription_checkout,
)
from extensions import db
from models import Usuario
from security import CSRF_HEADER_NAME, CSRF_SESSION_KEY, init_security


class StripeCheckoutTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="test-secret-key-with-at-least-32-characters",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            STRIPE_SECRET_KEY="sk_test_fake",
            STRIPE_PRO_PRICE_ID="price_pro",
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
        self.app.register_blueprint(main)
        self.app.register_blueprint(checkout_bp)
        with self.app.app_context():
            db.create_all()
            user = Usuario(email="stripe@example.com", nome="Stripe User")
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_route_requires_authentication(self):
        response = self.client.post("/api/billing/checkout", headers=self.csrf_headers())
        self.assertEqual(response.status_code, 401)

    def test_missing_price_fails_explicitly(self):
        with self.app.app_context():
            self.app.config["STRIPE_PRO_PRICE_ID"] = ""
            user = db.session.get(Usuario, self.user_id)
            with self.assertRaises(StripeConfigurationError):
                create_subscription_checkout(user, "https://example/s", "https://example/c")

    @patch("Blueprints.services.subscription.stripe_checkout_service.stripe.checkout.Session.create")
    @patch("Blueprints.services.subscription.stripe_checkout_service.stripe.Customer.create")
    def test_creates_customer_and_subscription_checkout(self, customer_create, session_create):
        customer_create.return_value = {"id": "cus_created"}
        session_create.return_value = {"id": "cs_created", "url": "https://checkout.stripe.com/c/pay/test"}
        with self.app.app_context():
            user = db.session.get(Usuario, self.user_id)
            result = create_subscription_checkout(user, "https://example/s", "https://example/c")
            self.assertEqual(result.checkout_url, "https://checkout.stripe.com/c/pay/test")
            self.assertEqual(user.stripe_customer_id, "cus_created")
        self.assertEqual(session_create.call_args.kwargs["mode"], "subscription")
        self.assertEqual(session_create.call_args.kwargs["line_items"], [{"price": "price_pro", "quantity": 1}])

    @patch("Blueprints.services.subscription.stripe_checkout_service.stripe.checkout.Session.create")
    @patch("Blueprints.services.subscription.stripe_checkout_service.stripe.Customer.create")
    def test_reuses_existing_customer(self, customer_create, session_create):
        session_create.return_value = {"id": "cs_existing", "url": "https://checkout.stripe.com/c/pay/existing"}
        with self.app.app_context():
            user = db.session.get(Usuario, self.user_id)
            user.stripe_customer_id = "cus_existing"
            db.session.commit()
            create_subscription_checkout(user, "https://example/s", "https://example/c")
        customer_create.assert_not_called()
        self.assertEqual(session_create.call_args.kwargs["customer"], "cus_existing")

    @patch("Blueprints.main.checkout_routes.create_subscription_checkout", side_effect=StripeCheckoutError("falha segura"))
    def test_provider_failure_is_safe(self, _service):
        self.login()
        response = self.client.post(
            "/api/billing/checkout",
            headers={**self.csrf_headers(), "Accept": "application/json"},
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json, {"ok": False, "error": "falha segura"})

    def login(self):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user_id)
            session["_fresh"] = True

    def csrf_headers(self):
        token = "test-csrf-token-with-enough-length-123"
        with self.client.session_transaction() as session:
            session[CSRF_SESSION_KEY] = token
        return {CSRF_HEADER_NAME: token}


if __name__ == "__main__":
    unittest.main()
