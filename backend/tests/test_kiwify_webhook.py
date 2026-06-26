import base64
import hashlib
import json
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from security import clear_rate_limit_state


KIWIFY_PRIVATE_KEY = ed25519.Ed25519PrivateKey.generate()
KIWIFY_PUBLIC_KEY = KIWIFY_PRIVATE_KEY.public_key()
KIWIFY_PUBLIC_KEY_PEM = KIWIFY_PUBLIC_KEY.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode("utf-8")


def _serialize_payload(payload: dict[str, object]) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def _signed_kiwify_headers(raw_body: str, timestamp_ms: int | None = None) -> dict[str, str]:
    timestamp_value = str(timestamp_ms or int(time.time() * 1000))
    message = f"/webhooks/kiwify:POST:{raw_body}:{timestamp_value}"
    digest = hashlib.sha256(message.encode("utf-8")).digest()
    signature = KIWIFY_PRIVATE_KEY.sign(digest)
    signature_value = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    return {
        "x-kiwify-digital-signature": signature_value,
        "x-kiwify-timestamp": timestamp_value,
    }


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

        with patch.dict(os.environ, {"KIWIFY_WEBHOOK_TOKEN": KIWIFY_PUBLIC_KEY_PEM}):
            response = self.client.post(
                "/webhooks/kiwify",
                headers=_signed_kiwify_headers(raw_body),
                content_type="application/json",
                data=raw_body,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"success": True})

    def test_query_signature_without_official_headers_returns_unauthorized(self) -> None:
        with patch.dict(os.environ, {"KIWIFY_WEBHOOK_TOKEN": KIWIFY_PUBLIC_KEY_PEM}):
            response = self.client.post(
                "/webhooks/kiwify?signature=test-token",
                json={"event": "subscription_renewed"},
            )

        self.assertEqual(response.status_code, 401)

    def test_missing_webhook_token_returns_unauthorized(self) -> None:
        raw_body = _serialize_payload({"webhook_event_type": "compra_aprovada"})

        with patch.dict(os.environ, {"KIWIFY_WEBHOOK_TOKEN": ""}):
            response = self.client.post(
                "/webhooks/kiwify",
                headers=_signed_kiwify_headers(raw_body),
                content_type="application/json",
                data=raw_body,
            )

        self.assertEqual(response.status_code, 401)

    def test_invalid_json_returns_bad_request(self) -> None:
        with patch.dict(os.environ, {"KIWIFY_WEBHOOK_TOKEN": KIWIFY_PUBLIC_KEY_PEM}):
            response = self.client.post(
                "/webhooks/kiwify",
                headers=_signed_kiwify_headers("{invalid-json"),
                content_type="application/json",
                data="{invalid-json",
            )

        self.assertEqual(response.status_code, 400)

    def test_reserialized_payload_signature_returns_unauthorized(self) -> None:
        payload = {"webhook_event_type": "compra_aprovada", "email": "cliente@example.com"}
        signed_body = _serialize_payload(payload)
        sent_body = json.dumps(payload, indent=2)

        with patch.dict(os.environ, {"KIWIFY_WEBHOOK_TOKEN": KIWIFY_PUBLIC_KEY_PEM}):
            response = self.client.post(
                "/webhooks/kiwify",
                headers=_signed_kiwify_headers(signed_body),
                content_type="application/json",
                data=sent_body,
            )

        self.assertEqual(response.status_code, 401)

    def test_invalid_signature_returns_unauthorized(self) -> None:
        raw_body = _serialize_payload({"webhook_event_type": "compra_aprovada"})
        headers = _signed_kiwify_headers(raw_body)
        headers["x-kiwify-digital-signature"] = "invalid-signature"

        with patch.dict(os.environ, {"KIWIFY_WEBHOOK_TOKEN": KIWIFY_PUBLIC_KEY_PEM}):
            response = self.client.post(
                "/webhooks/kiwify",
                headers=headers,
                content_type="application/json",
                data=raw_body,
            )

        self.assertEqual(response.status_code, 401)

    def test_expired_timestamp_returns_unauthorized(self) -> None:
        raw_body = _serialize_payload({"webhook_event_type": "compra_aprovada"})
        expired_timestamp_ms = int(time.time() * 1000) - 301_000

        with patch.dict(os.environ, {"KIWIFY_WEBHOOK_TOKEN": KIWIFY_PUBLIC_KEY_PEM}):
            response = self.client.post(
                "/webhooks/kiwify",
                headers=_signed_kiwify_headers(raw_body, expired_timestamp_ms),
                content_type="application/json",
                data=raw_body,
            )

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
