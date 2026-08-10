import stripe
from Blueprints.services.subscription.stripe_webhook_handler import (
    StripeWebhookError,
    construct_event,
    process_event,
)
from extensions import db
from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

webhook_bp = Blueprint("webhook", __name__)


@webhook_bp.post("/api/webhooks/stripe")
def receive_stripe_webhook():
    payload = request.get_data(cache=False)
    signature = request.headers.get("Stripe-Signature", "")
    try:
        event = construct_event(payload, signature)
    except (ValueError, stripe.SignatureVerificationError):
        current_app.logger.warning("stripe_webhook_invalid_signature")
        return jsonify({"ok": False, "error": "invalid_signature"}), 400
    except StripeWebhookError:
        current_app.logger.error("stripe_webhook_not_configured")
        return jsonify({"ok": False, "error": "webhook_unavailable"}), 503

    try:
        result = process_event(event)
    except StripeWebhookError as exc:
        db.session.rollback()
        current_app.logger.warning(
            "stripe_webhook_rejected event_type=%s reason=%s",
            getattr(event, "type", None) or event.get("type"),
            type(exc).__name__,
        )
        return jsonify({"ok": False, "error": "invalid_event"}), 400
    except stripe.StripeError as exc:
        db.session.rollback()
        current_app.logger.warning("stripe_webhook_api_failed error_type=%s", type(exc).__name__)
        return jsonify({"ok": False, "error": "provider_unavailable"}), 503
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error("stripe_webhook_database_failed error_type=%s", type(exc).__name__)
        return jsonify({"ok": False, "error": "database_unavailable"}), 503

    return jsonify(
        {
            "ok": True,
            "event_type": result.event_type,
            "status": result.status,
            "duplicate": result.duplicate,
        }
    ), 200
