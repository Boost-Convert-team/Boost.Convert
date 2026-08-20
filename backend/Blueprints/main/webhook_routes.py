from Blueprints.services.payments.mercado_pago_gateway import MercadoPagoRequestError
from Blueprints.services.payments.subscription_service import ProviderDataError
from Blueprints.services.payments.webhook_service import (
    WebhookConfigurationError,
    WebhookSignatureError,
    WebhookValidationError,
    process_notification,
    validate_webhook_signature,
)
from extensions import db
from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

webhook_bp = Blueprint("webhook", __name__)


@webhook_bp.post("/webhooks/mercado-pago")
def receive_mercado_pago_webhook():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        return jsonify({"ok": False, "error": "invalid_payload"}), 400

    query_id = str(
        request.args.get("data.id") or request.args.get("data_id") or ""
    ).strip()
    body_id = str(payload["data"].get("id") or "").strip()
    if not query_id or query_id != body_id:
        return jsonify({"ok": False, "error": "invalid_resource"}), 400

    request_id = str(request.headers.get("X-Request-Id") or "").strip()
    try:
        validate_webhook_signature(
            str(request.headers.get("X-Signature") or ""), request_id, query_id
        )
    except WebhookConfigurationError:
        current_app.logger.error("mercadopago_webhook_configuration_missing")
        return jsonify({"ok": False, "error": "webhook_unavailable"}), 503
    except WebhookSignatureError:
        current_app.logger.warning("mercadopago_webhook_invalid_signature")
        return jsonify({"ok": False, "error": "invalid_signature"}), 401

    try:
        result = process_notification(payload, query_id, request_id=request_id)
    except (WebhookValidationError, ProviderDataError) as exc:
        db.session.rollback()
        current_app.logger.warning(
            "mercadopago_webhook_rejected reason=%s resource_id=%s",
            type(exc).__name__,
            query_id,
        )
        return jsonify({"ok": False, "error": "invalid_resource"}), 400
    except MercadoPagoRequestError as exc:
        db.session.rollback()
        current_app.logger.warning(
            "mercadopago_webhook_sync_failed status=%s operation=%s "
            "provider_code=%s resource_id=%s",
            exc.status if exc.status is not None else "none",
            exc.operation,
            exc.provider_code,
            query_id,
        )
        return jsonify({"ok": False, "error": "provider_unavailable"}), 503
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error(
            "mercadopago_webhook_database_failed error_type=%s",
            type(exc).__name__,
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
