import json
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from security import clear_rate_limit_state


def _serialize_payload(payload: dict[str, object]) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


class KiwifyWebhookTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_rate_limit_state()
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def test_valid_webhook_returns_success(self) -> None:
        payload = {
            "webhook_event_type": "compra_aprovada",
            "email": "cliente@example.com",
        }
        raw_body = _serialize_payload(payload)

        response = self.client.post(
            "/webhooks/kiwify",
            content_type="application/json",
            data=raw_body,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"success": True})

    def test_invalid_query_signature_returns_success_temporarily(self) -> None:
        response = self.client.post(
            "/webhooks/kiwify?signature=wrong-token",
            json={"event": "subscription_renewed"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"success": True})

    def test_missing_signature_returns_success_temporarily(self) -> None:
        response = self.client.post(
            "/webhooks/kiwify",
            json={"webhook_event_type": "compra_aprovada"},
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
        response = self.client.post(
            "/webhooks/kiwify",
            json=["invalid-payload"],
        )

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
