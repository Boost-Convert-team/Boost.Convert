from __future__ import annotations

import json

from flask import Blueprint, Response, current_app, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from Blueprints.services.subscription.kiwify_subscription_service import sync_kiwify_user_plan

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

    # TODO: reativar validação oficial da assinatura Kiwify antes da produção final.
    sync_kiwify_user_plan(payload, current_app.logger)
    return jsonify({"success": True}), 200


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

