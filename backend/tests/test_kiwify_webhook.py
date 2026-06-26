import json
import sys
import unittest
from pathlib import Path

from flask import Flask
from werkzeug.test import TestResponse

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from extensions import db
from models import Usuario
from routes.kiwify_webhook import kiwify_webhook_bp


def _serialize_payload(payload: dict[str, object]) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


class KiwifyWebhookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.app.register_blueprint(kiwify_webhook_bp)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

    def tearDown(self) -> None:
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_valid_webhook_returns_success(self) -> None:
        payload = {
            "webhook_event_type": "order_approved",
            "Customer": {"email": "cliente@example.com"},
        }

        response = self.post_kiwify_payload(payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"success": True})

    def test_pro_events_set_user_plan_to_pro(self) -> None:
        for event in ("order_approved", "subscription_renewed"):
            with self.subTest(event=event):
                email = f"{event}@example.com"
                self.create_user(email, "free", "inactive")

                response = self.post_kiwify_payload(
                    {"webhook_event_type": event, "Customer": {"email": email.upper()}}
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.user_plan_state(email), ("pro", "active"))

    def test_free_events_set_user_plan_to_free(self) -> None:
        free_events = ("subscription_canceled", "chargeback", "compra_reembolsada", "refund")
        for event in free_events:
            with self.subTest(event=event):
                email = f"{event}@example.com"
                self.create_user(email, "pro", "active")

                response = self.post_kiwify_payload(
                    {"webhook_event_type": event, "Customer": {"email": email}}
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.user_plan_state(email), ("free", "inactive"))

    def test_unknown_user_returns_success_and_logs(self) -> None:
        payload = {
            "webhook_event_type": "order_approved",
            "Customer": {"email": "sem-cadastro@example.com"},
        }

        with self.assertLogs(self.app.logger.name, level="INFO") as captured_logs:
            response = self.post_kiwify_payload(payload)

        self.assertEqual(response.status_code, 200)
        self.assertIn("kiwify_webhook_user_not_found", "\n".join(captured_logs.output))

    def test_invalid_query_signature_returns_success_temporarily(self) -> None:
        response = self.client.post(
            "/webhooks/kiwify?signature=wrong-token",
            json={"event": "subscription_renewed", "Customer": {"email": "x@example.com"}},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"success": True})

    def test_missing_signature_returns_success_temporarily(self) -> None:
        response = self.client.post(
            "/webhooks/kiwify",
            json={"webhook_event_type": "order_approved"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"success": True})

    def test_invalid_json_returns_bad_request(self) -> None:
        response = self.client.post(
            "/webhooks/kiwify?signature=wrong-token",
            content_type="application/json",
            data="{invalid-json",
        )

        self.assertEqual(response.status_code, 400)

    def test_non_object_json_returns_bad_request(self) -> None:
        response = self.client.post("/webhooks/kiwify", json=["invalid-payload"])

        self.assertEqual(response.status_code, 400)

    def create_user(self, email: str, plano: str, status_assinatura: str) -> None:
        with self.app.app_context():
            user = Usuario(
                email=email,
                senha=None,
                plano=plano,
                status_assinatura=status_assinatura,
            )
            db.session.add(user)
            db.session.commit()

    def user_plan_state(self, email: str) -> tuple[str, str]:
        with self.app.app_context():
            user = Usuario.query.filter_by(email=email).one()
            return user.plano, user.status_assinatura

    def post_kiwify_payload(self, payload: dict[str, object]) -> TestResponse:
        return self.client.post(
            "/webhooks/kiwify",
            content_type="application/json",
            data=_serialize_payload(payload),
        )


if __name__ == "__main__":
    unittest.main()
