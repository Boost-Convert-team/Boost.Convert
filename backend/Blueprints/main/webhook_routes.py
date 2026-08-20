from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from Blueprints.services.payments.mercado_pago_client import MercadoPagoError
from Blueprints.services.payments.webhook_service import (
    SUPPORTED_EVENT_TYPES,
    WebhookConfigurationError,
    WebhookSignatureError,
    WebhookValidationError,
    process_payment_notification,
    process_subscription_notification,
    validate_webhook_signature,
)
from extensions import db

webhook_bp = Blueprint("webhook", __name__)


@webhook_bp.post("/webhooks/mercado-pago")
def receive_mercado_pago_webhook():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "invalid_payload"}), 400

    resource = payload.get("data")
    if not isinstance(resource, dict):
        return jsonify({"ok": False, "error": "invalid_resource"}), 400

    query_resource_id = str(
        request.args.get("data.id") or request.args.get("data_id") or ""
    ).strip()
    body_resource_id = str(resource.get("id") or "").strip()
    if not query_resource_id or query_resource_id != body_resource_id:
        return jsonify({"ok": False, "error": "invalid_resource"}), 400

    request_id = request.headers.get("X-Request-Id", "")
    try:
        validate_webhook_signature(
            request.headers.get("X-Signature", ""),
            request_id,
            query_resource_id,
        )
    except WebhookConfigurationError:
        current_app.logger.error("payment_webhook_configuration_missing")
        return jsonify({"ok": False, "error": "webhook_unavailable"}), 503
    except WebhookSignatureError:
        current_app.logger.warning("payment_webhook_invalid_signature")
        return jsonify({"ok": False, "error": "invalid_signature"}), 401

    try:
        processor = (
            process_subscription_notification
            if str(payload.get("type") or "").strip() in SUPPORTED_EVENT_TYPES
            else process_payment_notification
        )
        result = processor(payload, query_resource_id, request_id=request_id)
    except WebhookValidationError as exc:
        db.session.rollback()
        current_app.logger.warning(
            "payment_webhook_rejected reason=%s", type(exc).__name__
        )
        return jsonify({"ok": False, "error": "invalid_payment"}), 400
    except MercadoPagoError as exc:
        db.session.rollback()
        current_app.logger.warning(
            "mercadopago_webhook_sync_failed status=%s operation=%s endpoint=%s "
            "provider_code=%s resource_id=%s",
            exc.status if exc.status is not None else "none",
            exc.operation,
            exc.endpoint,
            exc.provider_code,
            query_resource_id,
        )
        return jsonify({"ok": False, "error": "provider_unavailable"}), 503
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error(
            "payment_webhook_database_failed error_type=%s", type(exc).__name__
        )
        return jsonify({"ok": False, "error": "database_unavailable"}), 503

    return jsonify(
        {
            "ok": True,
            "event_type": result.event_type,
            "status": result.status,
            "duplicate": result.duplicate,
        }
    ), 200
