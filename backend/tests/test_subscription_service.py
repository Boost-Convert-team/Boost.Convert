import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.subscription.subscription_service import (
    get_pro_access_state,
    has_active_pro_subscription,
)
from extensions import db
from models import Payment, Subscription, Usuario


class SubscriptionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="test-secret-with-enough-length-123",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)

    def tearDown(self) -> None:
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_legacy_pro_user_keeps_access_when_billing_tables_are_missing(self) -> None:
        with self.app.app_context():
            Usuario.__table__.create(db.engine)
            user = self.create_user("legacy-pro@example.com", "pro", "active")

            self.assertTrue(has_active_pro_subscription(user))
            self.assertTrue(db.session.is_active)

    def test_one_time_payment_is_active_for_30_days_but_not_at_expiration(self) -> None:
        approved_at = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        expires_at = approved_at + timedelta(days=30)
        with self.app.app_context():
            db.create_all()
            user = self.create_user("pix-30-days@example.com", "free", "inactive")
            db.session.add(
                Payment(
                    user_id=user.id,
                    provider_payment_id="pay_30_days",
                    payment_method="pix",
                    status="approved",
                    approved_at=approved_at,
                    premium_expires_at=expires_at,
                )
            )
            db.session.commit()

            active_state = get_pro_access_state(
                user,
                now=expires_at - timedelta(microseconds=1),
            )
            expired_state = get_pro_access_state(user, now=expires_at)

            self.assertTrue(active_state.active)
            self.assertEqual(active_state.source, "payment")
            self.assertFalse(expired_state.active)

    def test_expired_payment_downgrades_stale_user_flags(self) -> None:
        with self.app.app_context():
            db.create_all()
            user = self.create_user("expired@example.com", "pro", "active")
            db.session.add(
                Payment(
                    user_id=user.id,
                    provider_payment_id="pay_expired",
                    payment_method="pix",
                    status="approved",
                    approved_at=datetime.now(timezone.utc) - timedelta(days=31),
                    premium_expires_at=datetime.now(timezone.utc) - timedelta(days=1),
                )
            )
            db.session.commit()

            self.assertFalse(has_active_pro_subscription(user))
            db.session.expire_all()
            persisted_user = db.session.get(Usuario, user.id)
            self.assertEqual(
                (persisted_user.plano, persisted_user.status_assinatura),
                ("free", "inactive"),
            )

    def test_valid_payment_repairs_stale_free_flags(self) -> None:
        with self.app.app_context():
            db.create_all()
            user = self.create_user("paid@example.com", "free", "inactive")
            db.session.add(
                Payment(
                    user_id=user.id,
                    provider_payment_id="pay_active",
                    payment_method="credit_card",
                    status="approved",
                    approved_at=datetime.now(timezone.utc),
                    premium_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                )
            )
            db.session.commit()

            self.assertTrue(has_active_pro_subscription(user))
            self.assertEqual((user.plano, user.status_assinatura), ("pro", "active"))

    def test_authorized_subscription_without_approved_invoice_has_no_access(self) -> None:
        with self.app.app_context():
            db.create_all()
            user = self.create_user("authorized-only@example.com", "pro", "active")
            db.session.add(
                Subscription(
                    user_id=user.id,
                    provider_subscription_id="sub_without_payment",
                    status="authorized",
                    next_payment_at=datetime.now(timezone.utc) + timedelta(days=30),
                )
            )
            db.session.commit()

            self.assertFalse(has_active_pro_subscription(user))
            self.assertEqual((user.plano, user.status_assinatura), ("free", "inactive"))

    def test_paid_recurring_subscription_expires_at_paid_through_date(self) -> None:
        paid_through_at = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
        with self.app.app_context():
            db.create_all()
            user = self.create_user("recurring@example.com", "free", "inactive")
            db.session.add(
                Subscription(
                    user_id=user.id,
                    provider_subscription_id="sub_paid",
                    provider_payment_id="pay_subscription",
                    status="authorized",
                    latest_payment_status="approved",
                    paid_through_at=paid_through_at,
                )
            )
            db.session.commit()

            active_state = get_pro_access_state(
                user,
                now=paid_through_at - timedelta(seconds=1),
            )
            expired_state = get_pro_access_state(user, now=paid_through_at)

            self.assertTrue(active_state.active)
            self.assertEqual(active_state.source, "recurring")
            self.assertFalse(expired_state.active)

    def create_user(self, email: str, plano: str, status_assinatura: str) -> Usuario:
        user = Usuario(
            email=email,
            senha=None,
            plano=plano,
            status_assinatura=status_assinatura,
        )
        db.session.add(user)
        db.session.commit()
        return user


if __name__ == "__main__":
    unittest.main()
