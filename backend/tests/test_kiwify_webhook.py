import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from routes.kiwify_webhook import _calculate_kiwify_signature
from security import clear_rate_limit_state


def _signed_kiwify_url(payload: dict[str, object], secret_token: str) -> str:
    signature = _calculate_kiwify_signature(payload, secret_token)
    return f"/webhooks/kiwify?signature={signature}"


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

        with patch.dict(os.environ, {"KIWIFY_WEBHOOK_TOKEN": "test-token"}):
            response = self.client.post(
                _signed_kiwify_url(payload, "test-token"),
                content_type="application/json",
                data=json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"success": True})

    def test_calculate_kiwify_signature_uses_official_hmac_sha1(self) -> None:
        payload = {
            "webhook_event_type": "compra_aprovada",
            "email": "cliente@example.com",
        }

        signature = _calculate_kiwify_signature(payload, "test-token")

        self.assertEqual(signature, "662debd91ed359eb6b4b77344d40b5cab050b172")

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

    def test_plain_token_signature_returns_unauthorized(self) -> None:
        with patch.dict(os.environ, {"KIWIFY_WEBHOOK_TOKEN": "test-token"}):
            response = self.client.post(
                "/webhooks/kiwify?signature=test-token",
                json={"webhook_event_type": "compra_aprovada"},
            )

        self.assertEqual(response.status_code, 401)

    def test_invalid_signature_returns_unauthorized(self) -> None:
        with patch.dict(os.environ, {"KIWIFY_WEBHOOK_TOKEN": "test-token"}):
            response = self.client.post(
                "/webhooks/kiwify?signature=wrong-token",
                json={"webhook_event_type": "compra_aprovada"},
            )

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
