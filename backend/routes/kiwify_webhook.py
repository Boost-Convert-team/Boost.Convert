from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import time

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from flask import Blueprint, Response, current_app, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType


KIWIFY_EVENT_FIELDS = ("webhook_event_type", "event", "type")
KIWIFY_PUBLIC_KEY_ENV = "KIWIFY_WEBHOOK_TOKEN"
KIWIFY_SIGNATURE_HEADER = "x-kiwify-digital-signature"
KIWIFY_TIMESTAMP_HEADER = "x-kiwify-timestamp"
KIWIFY_TIMESTAMP_TOLERANCE_MS = 300_000

kiwify_webhook_bp = Blueprint("kiwify_webhook", __name__)


@kiwify_webhook_bp.route("/webhooks/kiwify", methods=["POST"])
def receive_kiwify_webhook() -> tuple[Response, int]:
    """Receive Kiwify events for the future subscription sync.

    Example: client.post("/webhooks/kiwify", json={"webhook_event_type": "compra_aprovada"})
    """
    raw_body = request.get_data(cache=True)
    payload = _read_kiwify_payload()
    _log_kiwify_request(payload)

    if payload is None:
        return jsonify({"success": False}), 400

    if not _is_kiwify_signature_valid(raw_body):
        return jsonify({"success": False}), 401

    _stage_kiwify_event(payload)
    return jsonify({"success": True}), 200


def _is_kiwify_signature_valid(raw_body: bytes) -> bool:
    public_key_value = os.getenv(KIWIFY_PUBLIC_KEY_ENV, "").strip()
    signature_value = request.headers.get(KIWIFY_SIGNATURE_HEADER, "").strip()
    timestamp_value = request.headers.get(KIWIFY_TIMESTAMP_HEADER, "").strip()
    if not public_key_value or not signature_value or not timestamp_value:
        return False
    if not _is_kiwify_timestamp_valid(timestamp_value):
        return False
    return _verify_kiwify_signature(raw_body, signature_value, timestamp_value, public_key_value)


def _is_kiwify_timestamp_valid(timestamp_value: str) -> bool:
    try:
        timestamp_ms = int(timestamp_value)
    except ValueError:
        return False
    now_ms = int(time.time() * 1000)
    return abs(now_ms - timestamp_ms) <= KIWIFY_TIMESTAMP_TOLERANCE_MS


def _verify_kiwify_signature(
    raw_body: bytes,
    signature_value: str,
    timestamp_value: str,
    public_key_value: str,
) -> bool:
    signature = _decode_kiwify_signature(signature_value)
    public_key = _load_kiwify_public_key(public_key_value)
    if signature is None or public_key is None:
        return False
    digest = hashlib.sha256(_build_kiwify_signed_message(raw_body, timestamp_value)).digest()
    try:
        public_key.verify(signature, digest)
    except InvalidSignature:
        return False
    return True


def _decode_kiwify_signature(signature_value: str) -> bytes | None:
    padding = (4 - len(signature_value) % 4) % 4
    try:
        return base64.urlsafe_b64decode(signature_value + "=" * padding)
    except (binascii.Error, ValueError):
        return None


def _load_kiwify_public_key(public_key_value: str) -> ed25519.Ed25519PublicKey | None:
    public_key_pem = public_key_value.replace("\\n", "\n").encode("utf-8")
    try:
        public_key = serialization.load_pem_public_key(public_key_pem)
    except (UnsupportedAlgorithm, ValueError):
        return None
    if not isinstance(public_key, ed25519.Ed25519PublicKey):
        return None
    return public_key


def _build_kiwify_signed_message(raw_body: bytes, timestamp_value: str) -> bytes:
    raw_body_text = raw_body.decode("utf-8")
    message = f"{request.path}:POST:{raw_body_text}:{timestamp_value}"
    return message.encode("utf-8")


def _read_kiwify_payload() -> dict[str, object] | None:
    try:
        payload = request.get_json()
    except (BadRequest, UnsupportedMediaType):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _log_kiwify_request(payload: dict[str, object] | None) -> None:
    log_data = {
        "event": "kiwify_webhook_request_received",
        "request.headers": dict(request.headers),
        "request.args": request.args.to_dict(flat=False),
        "request.get_json": payload,
    }
    current_app.logger.debug(json.dumps(log_data, ensure_ascii=False))


def _extract_kiwify_event(payload: dict[str, object]) -> str:
    for field_name in KIWIFY_EVENT_FIELDS:
        event = payload.get(field_name)
        if isinstance(event, str):
            return event
    return ""


def _stage_kiwify_event(payload: dict[str, object]) -> None:
    event = _extract_kiwify_event(payload)
    # TODO: localizar usuario pelo e-mail recebido da Kiwify antes de aplicar regras de plano.
    if event == "compra_aprovada":
        # TODO: liberar Premium.
        return
    if event == "subscription_renewed":
        # TODO: manter/renovar Premium.
        return
    if event == "subscription_canceled":
        # TODO: cancelar Premium.
        return
    if event == "compra_reembolsada":
        # TODO: remover Premium por reembolso.
        return
    if event == "chargeback":
        # TODO: remover Premium por chargeback.
        return
    if event == "subscription_late":
        # TODO: marcar assinatura atrasada.
        return
