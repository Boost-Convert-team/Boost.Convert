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
from models import Payment, Subscription, Usuario
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
    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.get_subscription"
    )
    def test_duplicate_key_reuses_checkout_once(
        self, get_subscription, create_checkout
    ):
        create_checkout.return_value = SubscriptionCheckout(
            "sub-1",
            "https://www.mercadopago.com.br/subscriptions/checkout"
            "?preapproval_id=sub-1",
            "pending",
        )
        self.login()
        key = str(uuid4())
        first = self.post_checkout(idempotency_key=key)
        with self.app.app_context():
            subscription = Subscription.query.filter_by(
                provider_subscription_id="sub-1"
            ).one()
            get_subscription.return_value = self.provider_subscription(
                subscription, "pending"
            )
        second = self.post_checkout(idempotency_key=key)
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(first.json["checkout_url"], second.json["checkout_url"])
        create_checkout.assert_called_once()
        get_subscription.assert_called_once_with("sub-1")

    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.get_subscription"
    )
    def test_legacy_pending_subscription_recovers_missing_checkout_url(
        self, get_subscription
    ):
        with self.app.app_context():
            subscription = self.subscription(
                self.user_id,
                "sub-legacy",
                status="pending",
                plan="BOOSTCONVERT_PRO",
            )
            get_subscription.return_value = self.provider_subscription(
                subscription, "pending"
            )
        self.login()

        response = self.post_checkout()

        self.assertEqual(response.status_code, 200)
        self.assertIn("sub-legacy", response.json["checkout_url"])
        with self.app.app_context():
            stored = Subscription.query.filter_by(
                provider_subscription_id="sub-legacy"
            ).one()
            self.assertEqual(stored.status, "pending")
            self.assertEqual(stored.checkout_url, response.json["checkout_url"])

    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.create_subscription_checkout"
    )
    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.cancel_subscription"
    )
    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.get_subscription"
    )
    def test_recent_pending_checkout_is_verified_before_reuse(
        self, get_subscription, cancel_subscription, create_checkout
    ):
        with self.app.app_context():
            subscription = self.subscription(
                self.user_id,
                "sub-recent",
                status="pending",
                checkout_url="https://www.mercadopago.com.br/old-checkout",
            )
            provider_subscription = self.provider_subscription(subscription, "pending")
            get_subscription.return_value = provider_subscription
        self.login()

        response = self.post_checkout()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json["checkout_url"], provider_subscription["init_point"]
        )
        get_subscription.assert_called_once_with("sub-recent")
        cancel_subscription.assert_not_called()
        create_checkout.assert_not_called()
        with self.app.app_context():
            stored = Subscription.query.filter_by(
                provider_subscription_id="sub-recent"
            ).one()
            self.assertEqual(stored.checkout_url, provider_subscription["init_point"])

    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.create_subscription_checkout"
    )
    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.cancel_subscription"
    )
    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.get_subscription"
    )
    def test_stale_pending_checkout_is_canceled_and_replaced(
        self, get_subscription, cancel_subscription, create_checkout
    ):
        idempotency_key = str(uuid4())
        with self.app.app_context():
            old = self.subscription(
                self.user_id,
                "sub-stale",
                status="pending",
                checkout_url=(
                    "https://www.mercadopago.com.br/subscriptions/checkout"
                    "?preapproval_id=sub-stale"
                ),
            )
            stale_at = datetime.now(timezone.utc) - timedelta(minutes=10)
            old.created_at = stale_at
            old.updated_at = stale_at
            old.checkout_idempotency_key = idempotency_key
            db.session.commit()
            get_subscription.return_value = self.provider_subscription(old, "pending")
            cancel_subscription.return_value = {
                "id": old.provider_subscription_id,
                "external_reference": old.external_reference,
                "status": "canceled",
            }
        new_checkout_url = (
            "https://www.mercadopago.com.br/subscriptions/checkout"
            "?preapproval_id=sub-new"
        )
        create_checkout.return_value = SubscriptionCheckout(
            "sub-new", new_checkout_url, "pending"
        )
        self.login()

        response = self.post_checkout(idempotency_key=idempotency_key)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["checkout_url"], new_checkout_url)
        cancel_subscription.assert_called_once_with("sub-stale")
        create_checkout.assert_called_once()
        with self.app.app_context():
            old = Subscription.query.filter_by(
                provider_subscription_id="sub-stale"
            ).one()
            new = Subscription.query.filter_by(
                provider_subscription_id="sub-new"
            ).one()
            self.assertEqual(old.status, "canceled")
            self.assertIsNone(old.checkout_idempotency_key)
            self.assertEqual(new.checkout_url, new_checkout_url)
            self.assertEqual(new.checkout_idempotency_key, idempotency_key)

    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.create_subscription_checkout"
    )
    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.cancel_subscription",
        side_effect=MercadoPagoError(
            operation="subscription_cancel",
            endpoint="/preapproval/sub-stale",
            status=503,
            provider_code="service_unavailable",
            provider_message="temporary provider failure",
        ),
    )
    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.get_subscription"
    )
    def test_stale_pending_cancel_failure_preserves_local_record(
        self, get_subscription, _cancel_subscription, create_checkout
    ):
        old_checkout_url = (
            "https://www.mercadopago.com.br/subscriptions/checkout"
            "?preapproval_id=sub-stale"
        )
        with self.app.app_context():
            old = self.subscription(
                self.user_id,
                "sub-stale",
                status="pending",
                checkout_url=old_checkout_url,
            )
            stale_at = datetime.now(timezone.utc) - timedelta(minutes=10)
            old.created_at = stale_at
            old.updated_at = stale_at
            db.session.commit()
            get_subscription.return_value = self.provider_subscription(old, "pending")
        self.login()

        response = self.post_checkout()

        self.assertEqual(response.status_code, 502)
        create_checkout.assert_not_called()
        with self.app.app_context():
            stored = Subscription.query.filter_by(
                provider_subscription_id="sub-stale"
            ).one()
            self.assertEqual(stored.status, "pending")
            self.assertEqual(stored.checkout_url, old_checkout_url)
            self.assertIsNone(stored.canceled_at)
            self.assertEqual(Subscription.query.count(), 1)

    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.create_subscription_checkout"
    )
    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.get_subscription"
    )
    def test_nearby_requests_reuse_verified_pending_checkout(
        self, get_subscription, create_checkout
    ):
        with self.app.app_context():
            subscription = self.subscription(
                self.user_id,
                "sub-recent",
                status="pending",
                checkout_url="https://www.mercadopago.com.br/old-checkout",
            )
            get_subscription.return_value = self.provider_subscription(
                subscription, "pending"
            )
        self.login()

        first = self.post_checkout()
        second = self.post_checkout()

        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(first.json["checkout_url"], second.json["checkout_url"])
        self.assertEqual(get_subscription.call_count, 2)
        create_checkout.assert_not_called()

    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.create_subscription_checkout"
    )
    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.cancel_subscription"
    )
    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.get_subscription"
    )
    def test_legacy_pending_checkout_with_old_price_is_replaced(
        self, get_subscription, cancel_subscription, create_checkout
    ):
        with self.app.app_context():
            old = self.subscription(
                self.user_id,
                "sub-old-price",
                status="pending",
                plan="BOOSTCONVERT_PRO",
            )
            provider_subscription = self.provider_subscription(old, "pending")
            provider_subscription["auto_recurring"]["transaction_amount"] = 19.90
            get_subscription.return_value = provider_subscription
            cancel_subscription.return_value = {
                "id": old.provider_subscription_id,
                "external_reference": old.external_reference,
                "status": "canceled",
            }
        create_checkout.return_value = SubscriptionCheckout(
            "sub-current-price",
            "https://www.mercadopago.com.br/subscriptions/checkout"
            "?preapproval_id=sub-current-price",
            "pending",
        )
        self.login()

        response = self.post_checkout()

        self.assertEqual(response.status_code, 201)
        create_payload = create_checkout.call_args.args[0]
        self.assertEqual(create_payload["auto_recurring"]["transaction_amount"], 25.90)
        with self.app.app_context():
            old = Subscription.query.filter_by(
                provider_subscription_id="sub-old-price"
            ).one()
            current = Subscription.query.filter_by(
                provider_subscription_id="sub-current-price"
            ).one()
            self.assertEqual(old.status, "canceled")
            self.assertEqual(current.status, "pending")

    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.create_subscription_checkout"
    )
    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.get_subscription"
    )
    def test_pending_checkout_with_wrong_reference_fails_closed(
        self, get_subscription, create_checkout
    ):
        with self.app.app_context():
            old = self.subscription(
                self.user_id, "sub-wrong-reference", status="pending"
            )
            provider_subscription = self.provider_subscription(old, "pending")
            provider_subscription["external_reference"] = "boost:subscription:other"
            get_subscription.return_value = provider_subscription
        self.login()

        response = self.post_checkout()

        self.assertEqual(response.status_code, 502)
        create_checkout.assert_not_called()
        with self.app.app_context():
            stored = Subscription.query.filter_by(
                provider_subscription_id="sub-wrong-reference"
            ).one()
            self.assertEqual(stored.status, "pending")

    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.create_subscription_checkout"
    )
    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.get_subscription"
    )
    def test_provider_canceled_subscription_does_not_block_new_checkout(
        self, get_subscription, create_checkout
    ):
        with self.app.app_context():
            old = self.subscription(self.user_id, "sub-old", status="pending")
            get_subscription.return_value = self.provider_subscription(old, "canceled")
        create_checkout.return_value = SubscriptionCheckout(
            "sub-new",
            "https://www.mercadopago.com.br/subscriptions/checkout?id=sub-new",
            "pending",
        )
        self.login()

        response = self.post_checkout()

        self.assertEqual(response.status_code, 201)
        with self.app.app_context():
            self.assertEqual(
                Subscription.query.filter_by(provider_subscription_id="sub-old")
                .one()
                .status,
                "canceled",
            )
            self.assertEqual(Subscription.query.count(), 2)

    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.search_authorized_payments",
        return_value=[],
    )
    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.get_subscription"
    )
    def test_unpaid_authorized_subscription_is_never_replaceable(
        self, get_subscription, _search_invoices
    ):
        with self.app.app_context():
            subscription = self.subscription(self.user_id, "sub-unpaid")
            get_subscription.return_value = self.provider_subscription(
                subscription, "authorized"
            )
        self.login()

        response = self.post_checkout()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["code"], "unpaid_subscription")
        self.assertNotIn("can_replace", response.json)

    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.create_subscription_checkout"
    )
    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.cancel_subscription"
    )
    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.search_authorized_payments",
        return_value=[],
    )
    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.get_subscription"
    )
    def test_explicit_recovery_does_not_replace_authorized_subscription(
        self, get_subscription, _search_invoices, cancel, create_checkout
    ):
        with self.app.app_context():
            subscription = self.subscription(self.user_id, "sub-unpaid")
            get_subscription.return_value = self.provider_subscription(
                subscription, "authorized"
            )
        create_checkout.return_value = SubscriptionCheckout(
            "sub-retry",
            "https://www.mercadopago.com.br/subscriptions/checkout?id=sub-retry",
            "pending",
        )
        self.login()

        response = self.post_checkout(replace_unpaid_subscription=True)

        self.assertEqual(response.status_code, 409)
        cancel.assert_not_called()
        create_checkout.assert_not_called()
        with self.app.app_context():
            old = Subscription.query.filter_by(
                provider_subscription_id="sub-unpaid"
            ).one()
            self.assertEqual(old.status, "active")
            self.assertEqual(Subscription.query.count(), 1)

    def test_checkout_reconciles_approved_invoice_when_webhook_was_missed(self):
        with self.app.app_context():
            subscription = self.subscription(self.user_id, "sub-approved")
            provider_subscription = self.provider_subscription(
                subscription, "authorized"
            )
            invoice = {
                "id": "501",
                "preapproval_id": "sub-approved",
                "external_reference": subscription.external_reference,
                "transaction_amount": "25.90",
                "currency_id": "BRL",
                "date_created": "2026-08-17T12:00:00Z",
                "debit_date": "2026-08-17T12:00:00Z",
                "payment": {
                    "id": "9001",
                    "status": "approved",
                    "status_detail": "accredited",
                },
            }
        self.login()
        with (
            patch(
                "Blueprints.services.payments.payment_service."
                "MercadoPagoClient.get_subscription",
                return_value=provider_subscription,
            ),
            patch(
                "Blueprints.services.payments.payment_service."
                "MercadoPagoClient.search_authorized_payments",
                return_value=[invoice],
            ),
        ):
            response = self.post_checkout()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["code"], "subscription_already_paid")
        with self.app.app_context():
            user = db.session.get(Usuario, self.user_id)
            self.assertEqual((user.plano, user.status_assinatura), ("pro", "active"))
            self.assertEqual(Payment.query.count(), 1)

    @patch(
        "Blueprints.services.payments.payment_service."
        "MercadoPagoClient.create_subscription_checkout"
    )
    def test_stale_interrupted_creation_is_replaced(self, create_checkout):
        with self.app.app_context():
            db.session.add(
                Subscription(
                    user_id=self.user_id,
                    provider="mercado_pago",
                    external_reference=f"boost:subscription:{uuid4()}",
                    plan="PRO",
                    status="creating",
                    amount="25.90",
                    currency="BRL",
                    created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
                )
            )
            db.session.commit()
        create_checkout.return_value = SubscriptionCheckout(
            "sub-recovered",
            "https://www.mercadopago.com/subscriptions/checkout?id=sub-recovered",
            "pending",
        )
        self.login()

        response = self.post_checkout()

        self.assertEqual(response.status_code, 201)
        with self.app.app_context():
            statuses = [
                row.status for row in Subscription.query.order_by(Subscription.id)
            ]
            self.assertEqual(statuses, ["error", "pending"])

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
        self.assertIn("plan_id: payload.plan_id", payment_script)
        self.assertIn("replace_unpaid_subscription", payment_script)

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

    def subscription(
        self,
        user_id,
        provider_id,
        *,
        status="active",
        plan="PRO",
        checkout_url=None,
    ):
        subscription = Subscription(
            user_id=user_id,
            provider="mercado_pago",
            provider_subscription_id=provider_id,
            external_reference=f"boost:subscription:{uuid4()}",
            plan=plan,
            status=status,
            amount="25.90",
            currency="BRL",
            checkout_url=checkout_url,
        )
        db.session.add(subscription)
        db.session.commit()
        return subscription

    @staticmethod
    def provider_subscription(subscription, status):
        return {
            "id": subscription.provider_subscription_id,
            "external_reference": subscription.external_reference,
            "preapproval_plan_id": None,
            "status": status,
            "init_point": (
                "https://www.mercadopago.com.br/subscriptions/checkout"
                f"?preapproval_id={subscription.provider_subscription_id}"
            ),
            "date_created": "2026-08-17T12:00:00Z",
            "next_payment_date": "2026-09-17T12:00:00Z",
            "auto_recurring": {
                "frequency": 1,
                "frequency_type": "months",
                "transaction_amount": 25.90,
                "currency_id": "BRL",
            },
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
