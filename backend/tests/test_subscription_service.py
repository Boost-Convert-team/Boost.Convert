import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask
from sqlalchemy.exc import OperationalError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.subscription.subscription_service import (
    get_pro_access_state,
    has_active_pro_subscription,
)
from extensions import db
from models import Payment, Subscription, Usuario


class SubscriptionServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="test-secret-with-enough-length-123",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_missing_billing_schema_is_not_hidden(self):
        with self.app.app_context():
            Usuario.__table__.create(db.engine)
            user = self.user("legacy@example.com", "pro", "active")
            with self.assertRaises(OperationalError):
                has_active_pro_subscription(user)

    def test_active_paid_entitlement_grants_access_until_period_end(self):
        period_end = datetime.now(timezone.utc) + timedelta(days=30)
        with self.app.app_context():
            db.create_all()
            user = self.user("active@example.com")
            db.session.add(
                Subscription(
                    user_id=user.id,
                    provider="mercado_pago",
                    provider_subscription_id="sub_active",
                    status="active",
                    paid_through_at=period_end,
                )
            )
            db.session.commit()
            state = get_pro_access_state(user, now=period_end - timedelta(seconds=1))
            self.assertTrue(state.active)
            self.assertFalse(get_pro_access_state(user, now=period_end).active)

    def test_canceled_subscription_removes_stale_pro_flags(self):
        with self.app.app_context():
            db.create_all()
            user = self.user("canceled@example.com", "pro", "active")
            db.session.add(
                Subscription(
                    user_id=user.id,
                    provider="mercado_pago",
                    provider_subscription_id="sub_canceled",
                    status="canceled",
                    paid_through_at=datetime.now(timezone.utc) + timedelta(days=10),
                )
            )
            db.session.commit()
            self.assertFalse(has_active_pro_subscription(user))
            self.assertEqual((user.plano, user.status_assinatura), ("free", "inactive"))

    def test_approved_one_time_payment_grants_access_until_expiration(self):
        expiration = datetime.now(timezone.utc) + timedelta(days=30)
        with self.app.app_context():
            db.create_all()
            user = self.user("payment@example.com")
            attempt_id = "d1a1a780-91f4-43db-9398-c1247052931d"
            db.session.add(
                Payment(
                    user_id=user.id,
                    provider="mercado_pago",
                    provider_payment_id="123456",
                    external_reference=f"boost:payment:{user.id}:{attempt_id}",
                    plan="PRO",
                    attempt_id=attempt_id,
                    idempotency_key=attempt_id,
                    payment_method="credit_card",
                    status="approved",
                    amount="25.90",
                    currency="BRL",
                    premium_expires_at=expiration,
                )
            )
            db.session.commit()
            state = get_pro_access_state(user, now=expiration - timedelta(seconds=1))
            self.assertTrue(state.active)
            self.assertEqual(state.source, "payment")
            self.assertFalse(get_pro_access_state(user, now=expiration).active)

    def test_refunded_payment_does_not_grant_access(self):
        with self.app.app_context():
            db.create_all()
            user = self.user("refunded@example.com", "pro", "active")
            attempt_id = "4ca9719a-cb61-4e08-a4ef-e41071a3bfcc"
            db.session.add(
                Payment(
                    user_id=user.id,
                    provider="mercado_pago",
                    provider_payment_id="654321",
                    external_reference=f"boost:payment:{user.id}:{attempt_id}",
                    plan="PRO",
                    attempt_id=attempt_id,
                    idempotency_key=attempt_id,
                    payment_method="credit_card",
                    status="refunded",
                    amount="25.90",
                    currency="BRL",
                    premium_expires_at=datetime.now(timezone.utc) + timedelta(days=20),
                )
            )
            db.session.commit()
            self.assertFalse(has_active_pro_subscription(user))
            self.assertEqual((user.plano, user.status_assinatura), ("free", "inactive"))

    def user(self, email, plano="free", status="inactive"):
        user = Usuario(email=email, plano=plano, status_assinatura=status)
        db.session.add(user)
        db.session.commit()
        return user


if __name__ == "__main__":
    unittest.main()
