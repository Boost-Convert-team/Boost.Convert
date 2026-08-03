from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from Blueprints.services.subscription.mercado_pago_service import (
    MercadoPagoError,
    MercadoPagoHTTPError,
    MercadoPagoTimeoutError,
    process_mercado_pago_webhook,
    validate_mercado_pago_webhook_signature,
)

webhook_bp = Blueprint("webhook", __name__)
@webhook_bp.route("/webhook", methods=["POST"])
def legacy_webhook_disabled():
    return jsonify({"ok": False, "error": "webhook_disabled"}), 410

@webhook_bp.route("/webhooks/mercado-pago", methods=["POST"])
@webhook_bp.route("/api/webhooks/mercadopago", methods=["POST"])
def receive_mercado_pago_webhook():
    payload = read_json_payload()

    if payload is None: return jsonify({"ok": False, "error": "invalid_json"}), 400

    # TEMPORÁRIO - TESTE MERCADO PAGO
    # if not validate_mercado_pago_webhook_signature(payload):
    #     current_app.logger.warning("mercado_pago_webhook_invalid_signature")
    #     return jsonify({"ok": False, "error": "invalid_signature"}), 401

    try:
        result = process_mercado_pago_webhook(payload)

    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error(
            "mercado_pago_webhook_database_failed error_type=%s",
            type(exc).__name__,
        )

        return jsonify({"ok": False, "error": "payment_database_unavailable"}), 503
    
    except MercadoPagoHTTPError as exc:
        db.session.rollback()
        current_app.logger.warning(
            "mercado_pago_webhook_provider_http_failed provider_status=%s",
            exc.provider_status,
        )
        response = jsonify({"ok": False, "error": "provider_verification_failed"})

        if exc.retry_after:
            response.headers["Retry-After"] = exc.retry_after
        return response, exc.public_status
    
    except MercadoPagoTimeoutError:
        db.session.rollback()
        current_app.logger.warning("mercado_pago_webhook_provider_timeout")
        return jsonify({"ok": False, "error": "provider_temporarily_unavailable"}), 503
    
    except MercadoPagoError as exc:
        db.session.rollback()

        current_app.logger.exception(
            "mercado_pago_webhook_processing_failed message=%s code=%s cause=%s",
            str(exc),
            exc.code,
            exc.cause,
        )
        return jsonify({"ok": False, "error": "provider_verification_failed"}), 502

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
