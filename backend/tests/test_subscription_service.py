import sys
import unittest
from pathlib import Path

from flask import Flask


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.subscription.subscription_service import has_active_pro_subscription
from extensions import db
from models import Usuario


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
            user = Usuario(
                email="legacy-pro@example.com",
                plano="pro",
                status_assinatura="active",
            )
            db.session.add(user)
            db.session.commit()

            self.assertTrue(has_active_pro_subscription(user))
            self.assertTrue(db.session.is_active)


if __name__ == "__main__":
    unittest.main()
