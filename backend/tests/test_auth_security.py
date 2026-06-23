import sys
import unittest
from pathlib import Path

from flask import Flask


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.auth.authentication import authenticate_local_user, create_local_user
from extensions import db


class AuthSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="test-secret-with-enough-length-123",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        with self.app.app_context():
            db.create_all()

    def tearDown(self) -> None:
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_sql_injection_payload_does_not_authenticate_user(self) -> None:
        with self.app.app_context():
            create_local_user("owner@example.com", "correct-password")

            user = authenticate_local_user("' OR 1=1 --", "irrelevant")

        self.assertIsNone(user)


if __name__ == "__main__":
    unittest.main()
