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
                "/webhooks/kiwify",
                headers={"X-Kiwify-Webhook-Token": "test-token"},
                json={"email": "cliente@example.com", "webhook_event_type": "compra_aprovada"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"success": True})

    def test_valid_authorization_bearer_token_returns_success(self) -> None:
        with patch.dict(os.environ, {"KIWIFY_WEBHOOK_TOKEN": "test-token"}):
            response = self.client.post(
                "/webhooks/kiwify",
                headers={"Authorization": "Bearer test-token"},
                json={"event": "subscription_renewed"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"success": True})

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
                "/webhooks/kiwify",
                content_type="application/json",
                data="{invalid-json",
                headers={"X-Kiwify-Webhook-Token": "test-token"},
            )

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
