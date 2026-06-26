import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from security import clear_rate_limit_state


class KiwifyWebhookTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_rate_limit_state()
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def test_valid_webhook_returns_success(self) -> None:
        with patch.dict(os.environ, {"KIWIFY_WEBHOOK_TOKEN": "test-token"}):
            response = self.client.post(
                "/webhooks/kiwify?signature=test-token",
                json={"email": "cliente@example.com", "webhook_event_type": "compra_aprovada"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"success": True})

    def test_header_token_without_query_signature_returns_unauthorized(self) -> None:
        with patch.dict(os.environ, {"KIWIFY_WEBHOOK_TOKEN": "test-token"}):
            response = self.client.post(
                "/webhooks/kiwify",
                headers={"X-Kiwify-Webhook-Token": "test-token"},
                json={"event": "subscription_renewed"},
            )

        self.assertEqual(response.status_code, 401)

    def test_missing_webhook_token_returns_unauthorized(self) -> None:
        with patch.dict(os.environ, {"KIWIFY_WEBHOOK_TOKEN": "test-token"}):
            response = self.client.post(
                "/webhooks/kiwify",
                json={"webhook_event_type": "compra_aprovada"},
            )

        self.assertEqual(response.status_code, 401)

    def test_invalid_json_returns_bad_request(self) -> None:
        with patch.dict(os.environ, {"KIWIFY_WEBHOOK_TOKEN": "test-token"}):
            response = self.client.post(
                "/webhooks/kiwify?signature=test-token",
                content_type="application/json",
                data="{invalid-json",
            )

        self.assertEqual(response.status_code, 400)

    def test_invalid_signature_returns_unauthorized(self) -> None:
        with patch.dict(os.environ, {"KIWIFY_WEBHOOK_TOKEN": "test-token"}):
            response = self.client.post(
                "/webhooks/kiwify?signature=wrong-token",
                json={"webhook_event_type": "compra_aprovada"},
            )

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
