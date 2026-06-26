from __future__ import annotations

import hashlib
import hmac
import json
import os

from flask import Blueprint, Response, current_app, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType


KIWIFY_EVENT_FIELDS = ("webhook_event_type", "event", "type")
KIWIFY_SIGNATURE_ARG = "signature"

kiwify_webhook_bp = Blueprint("kiwify_webhook", __name__)


@kiwify_webhook_bp.route("/webhooks/kiwify", methods=["POST"])
def receive_kiwify_webhook() -> tuple[Response, int]:
    """Receive Kiwify events for the future subscription sync.

    Example: client.post("/webhooks/kiwify", json={"webhook_event_type": "compra_aprovada"})
    """
    payload = _read_kiwify_payload()
    _log_kiwify_request(payload)

    if payload is None:
        return jsonify({"success": False}), 400

    if not _is_kiwify_signature_valid(payload):
        return jsonify({"success": False}), 401

    _stage_kiwify_event(payload)
    return jsonify({"success": True}), 200


def _is_kiwify_signature_valid(payload: dict[str, object]) -> bool:
    secret_token = os.getenv("KIWIFY_WEBHOOK_TOKEN", "").strip()
    submitted_signature = request.args.get(KIWIFY_SIGNATURE_ARG, "").strip()
    if not secret_token or not submitted_signature:
        return False
    calculated_signature = _calculate_kiwify_signature(payload, secret_token)
    return hmac.compare_digest(calculated_signature, submitted_signature)


def _calculate_kiwify_signature(payload: dict[str, object], secret_token: str) -> str:
    canonical_payload = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(
        secret_token.encode("utf-8"),
        canonical_payload.encode("utf-8"),
        hashlib.sha1,
    ).hexdigest()


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
