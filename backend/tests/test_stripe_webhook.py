import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from flask import Flask

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.main.webhook_routes import webhook_bp
from Blueprints.services.subscription.stripe_webhook_handler import process_event
from extensions import db
from models import PaymentWebhookEvent, Subscription, Usuario
from security import init_security


class StripeWebhookTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="test-secret-key-with-at-least-32-characters",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            STRIPE_SECRET_KEY="sk_test_fake",
            STRIPE_WEBHOOK_SECRET="whsec_test",
            STRIPE_PRO_PRICE_ID="price_pro",
            CSRF_ENABLED=True,
            RATE_LIMIT_ENABLED=False,
            FORCE_HTTPS=False,
        )
        db.init_app(self.app)
        init_security(self.app)
        self.app.register_blueprint(webhook_bp)
        with self.app.app_context():
            db.create_all()
            user = Usuario(email="webhook@example.com", stripe_customer_id="cus_user")
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_invalid_signature_changes_nothing(self):
        response = self.client.post(
            "/api/webhooks/stripe",
            data=b"{}",
            headers={"Stripe-Signature": "invalid"},
        )
        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            self.assertEqual(PaymentWebhookEvent.query.count(), 0)

    def test_checkout_completed_associates_but_does_not_grant_pro(self):
        with self.app.app_context():
            process_event(self.event("evt_checkout", "checkout.session.completed", {
                "id": "cs_test", "mode": "subscription", "customer": "cus_user",
                "subscription": "sub_user", "metadata": self.metadata(),
            }))
            user = db.session.get(Usuario, self.user_id)
            subscription = Subscription.query.one()
            self.assertEqual(subscription.status, "pending")
            self.assertEqual(user.plano, "free")

    def test_invoice_paid_activates_and_renews(self):
        period_end = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        with self.app.app_context(), patch(
            "Blueprints.services.subscription.stripe_webhook_handler.stripe.Subscription.retrieve",
            return_value=self.subscription(status="active", period_end=period_end),
        ):
            result = process_event(self.event("evt_paid", "invoice.paid", self.invoice(period_end)))
            subscription = Subscription.query.one()
            user = db.session.get(Usuario, self.user_id)
            self.assertEqual(result.status, "processed")
            self.assertEqual(subscription.latest_payment_status, "paid")
            self.assertEqual(user.plano, "pro")

            duplicate = process_event(self.event("evt_paid", "invoice.paid", self.invoice(period_end)))
            self.assertTrue(duplicate.duplicate)
            self.assertEqual(PaymentWebhookEvent.query.count(), 1)

    def test_payment_failed_uses_real_subscription_state(self):
        period_end = int((datetime.now(timezone.utc) + timedelta(days=5)).timestamp())
        with self.app.app_context(), patch(
            "Blueprints.services.subscription.stripe_webhook_handler.stripe.Subscription.retrieve",
            return_value=self.subscription(status="past_due", period_end=period_end),
        ):
            db.session.add(
                Subscription(
                    user_id=self.user_id,
                    provider="stripe",
                    provider_subscription_id="sub_user",
                    status="active",
                    stripe_price_id="price_pro",
                    paid_through_at=datetime.fromtimestamp(period_end, timezone.utc),
                )
            )
            db.session.commit()
            process_event(self.event("evt_failed", "invoice.payment_failed", self.invoice(period_end)))
            subscription = Subscription.query.one()
            self.assertEqual(subscription.latest_payment_status, "failed")
            self.assertEqual(db.session.get(Usuario, self.user_id).plano, "pro")

    def test_subscription_updated_and_deleted_sync_access(self):
        period_end = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        with self.app.app_context():
            db.session.add(
                Subscription(
                    user_id=self.user_id,
                    provider="stripe",
                    provider_subscription_id="sub_user",
                    status="active",
                    stripe_price_id="price_pro",
                    paid_through_at=datetime.fromtimestamp(period_end, timezone.utc),
                )
            )
            db.session.commit()
            process_event(self.event("evt_updated", "customer.subscription.updated", self.subscription("active", period_end)))
            self.assertEqual(db.session.get(Usuario, self.user_id).plano, "pro")
            process_event(self.event("evt_deleted", "customer.subscription.deleted", self.subscription("canceled", period_end)))
            self.assertEqual(db.session.get(Usuario, self.user_id).plano, "free")
            self.assertEqual(Subscription.query.one().status, "canceled")

    def test_unknown_event_is_idempotently_ignored(self):
        with self.app.app_context():
            result = process_event(self.event("evt_unknown", "customer.created", {"id": "cus_user"}))
            self.assertEqual(result.status, "ignored")
            self.assertEqual(Subscription.query.count(), 0)

    def metadata(self):
        return {"boostconvert_user_id": str(self.user_id)}

    def subscription(self, status, period_end):
        return {
            "id": "sub_user", "customer": "cus_user", "status": status,
            "metadata": self.metadata(), "cancel_at_period_end": False,
            "items": {"data": [{"price": {"id": "price_pro"}, "current_period_end": period_end}]},
        }

    def invoice(self, period_end):
        return {
            "id": "in_test", "customer": "cus_user",
            "parent": {"subscription_details": {"subscription": "sub_user", "metadata": self.metadata()}},
            "lines": {"data": [{"period": {"end": period_end}}]},
        }

    @staticmethod
    def event(event_id, event_type, obj):
        return {"id": event_id, "type": event_type, "livemode": False, "data": {"object": obj}}


if __name__ == "__main__":
    unittest.main()
