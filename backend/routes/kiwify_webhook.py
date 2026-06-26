from __future__ import annotations

import hmac
import json
import os

from flask import Blueprint, Response, current_app, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType


KIWIFY_EVENT_FIELDS = ("webhook_event_type", "event", "type")
KIWIFY_TOKEN_HEADERS = ("X-Kiwify-Webhook-Token", "X-Kiwify-Token")

kiwify_webhook_bp = Blueprint("kiwify_webhook", __name__)


@kiwify_webhook_bp.route("/webhooks/kiwify", methods=["POST"])
def receive_kiwify_webhook() -> tuple[Response, int]:
    """Receive Kiwify events for the future subscription sync.

    Example: client.post("/webhooks/kiwify", json={"webhook_event_type": "compra_aprovada"})
    """
    if not _is_kiwify_token_valid():
        return jsonify({"success": False}), 401

    payload = _read_kiwify_payload()
    if payload is None:
        return jsonify({"success": False}), 400

    _log_kiwify_payload(payload)
    _stage_kiwify_event(payload)
    return jsonify({"success": True}), 200


def _is_kiwify_token_valid() -> bool:
    expected_token = os.getenv("KIWIFY_WEBHOOK_TOKEN", "").strip()
    submitted_token = _get_submitted_kiwify_token()
    if not expected_token or not submitted_token:
        return False
    return hmac.compare_digest(expected_token, submitted_token)


def _get_submitted_kiwify_token() -> str:
    for header_name in KIWIFY_TOKEN_HEADERS:
        submitted_token = request.headers.get(header_name, "").strip()
        if submitted_token:
            return submitted_token
    return _normalize_authorization_token(request.headers.get("Authorization", ""))


def _normalize_authorization_token(header_value: str) -> str:
    token = header_value.strip()
    if token.lower().startswith("bearer "):
        return token[7:].strip()
    return token


def _read_kiwify_payload() -> dict[str, object] | None:
    try:
        payload = request.get_json()
    except (BadRequest, UnsupportedMediaType):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _log_kiwify_payload(payload: dict[str, object]) -> None:
    log_data = {"event": "kiwify_webhook_payload_received", "payload": payload}
    current_app.logger.info(json.dumps(log_data, ensure_ascii=False))


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
