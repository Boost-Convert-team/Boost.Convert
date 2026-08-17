import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from config import Config, is_weak_secret_key
from security import CSRF_FIELD_NAME, CSRF_SESSION_KEY, clear_rate_limit_state


class SecurityMiddlewareTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_rate_limit_state()
        Config.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        Config.SQLALCHEMY_ENGINE_OPTIONS = {}
        self.app = create_app()
        self.app.config.update(TESTING=True)
        with self.app.app_context():
            from extensions import db

            db.create_all()
        self.client = self.app.test_client()

    def test_post_without_csrf_token_is_blocked(self) -> None:
        response = self.client.post(
            "/login", data={"nomeForm": "a@b.com", "senhaForm": "x"}
        )

        self.assertEqual(response.status_code, 400)

    def test_security_headers_are_present(self) -> None:
        response = self.client.get("/")

        content_security_policy = response.headers["Content-Security-Policy"]
        self.assertIn("frame-src 'none'", content_security_policy)
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("geolocation=()", response.headers["Permissions-Policy"])

    def test_login_rate_limit_blocks_repeated_attempts(self) -> None:
        responses = [
            self.client.post(
                "/login",
                data=self.csrf_data(
                    {"nomeForm": "nobody@example.com", "senhaForm": "bad"}
                ),
                environ_overrides={"REMOTE_ADDR": "203.0.113.77"},
            )
            for _index in range(6)
        ]

        self.assertEqual(responses[-1].status_code, 429)

    def test_weak_secret_key_detection_rejects_short_values(self) -> None:
        self.assertTrue(is_weak_secret_key("dev"))
        self.assertTrue(is_weak_secret_key("short"))
        self.assertFalse(is_weak_secret_key("a-secure-test-secret-key-with-32-chars"))

    def test_payment_webhook_requires_secret(self) -> None:
        self.app.config.update(MERCADOPAGO_WEBHOOK_SECRET=None)

        response = self.client.post(
            "/webhooks/mercado-pago?data.id=sub-123",
            json={
                "id": 1,
                "type": "subscription_preapproval",
                "action": "updated",
                "data": {"id": "sub-123"},
            },
            headers={"X-Signature": "invalid"},
        )

        self.assertEqual(response.status_code, 503)

    def test_private_checkout_route_requires_login_with_valid_csrf(self) -> None:
        response = self.client.post("/api/payments/checkout", data=self.csrf_data())

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def csrf_data(self, data: dict[str, str] | None = None) -> dict[str, str]:
        token = "test-csrf-token-with-enough-length-123"
        with self.client.session_transaction() as session:
            session[CSRF_SESSION_KEY] = token
        return {**(data or {}), CSRF_FIELD_NAME: token}


if __name__ == "__main__":
    unittest.main()
