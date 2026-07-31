from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from extensions import db
from Blueprints.services.subscription.mercado_pago_service import (
    MercadoPagoError,
    process_mercado_pago_webhook,
    validate_mercado_pago_webhook_signature,
)

webhook_bp = Blueprint("webhook", __name__)
@webhook_bp.route("/webhook", methods=["POST"])
def webhook(): return jsonify({"ok": True})

@webhook_bp.route("/webhooks/mercado-pago", methods=["POST"])
@webhook_bp.route("/api/webhooks/mercadopago", methods=["POST"])
def receive_mercado_pago_webhook():
    payload = read_json_payload()
    if payload is None:
        return jsonify({"ok": False, "error": "invalid_json"}), 400

    if not validate_mercado_pago_webhook_signature(payload):
        current_app.logger.warning("mercado_pago_webhook_invalid_signature")
        return jsonify({"ok": False, "error": "invalid_signature"}), 401

    try:
        result = process_mercado_pago_webhook(payload)
    except MercadoPagoError as exc:
        db.session.rollback()
        current_app.logger.warning("mercado_pago_webhook_processing_failed error=%s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 502

    return jsonify(
        {
            "ok": True,
            "plan_name": "BoostConvert PRO",
            "status": result.status,
            "event_type": result.event_type,
            "resource_id": result.resource_id,
            "duplicate": result.duplicate,
        }
    ), 200


def read_json_payload() -> dict[str, object] | None:
    try:
        payload = request.get_json()
    except (BadRequest, UnsupportedMediaType):
        return None
    if not isinstance(payload, dict):
        return None
    return payload
