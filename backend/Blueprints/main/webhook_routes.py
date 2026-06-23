import hmac

from flask import Blueprint, current_app, jsonify, request
from extensions import db
from models import Usuario

webhook_bp = Blueprint("webhook", __name__)
@webhook_bp.route("/webhook", methods=["POST"])
def webhook(): return jsonify({"ok": True})

@webhook_bp.route("/webhook/payment", methods=["POST"])
def payment_webhook():
    if not is_payment_webhook_authorized():
        return jsonify({"ok": False}), 403

    payload = request.get_json(silent=True) if request.is_json else {}
    user_id = request.form.get("user_id") or payload.get("user_id")
    event = request.form.get("event") or payload.get("event")
    if event != "payment_approved": return jsonify({"ok": True})

    user = db.session.get(Usuario, int(user_id)) if user_id else None
    if user is None: return jsonify({"ok": False}), 404
    
    user.plano = "pro"
    user.status_assinatura = "active"
    db.session.commit()
    return jsonify({"ok": True})


def is_payment_webhook_authorized() -> bool:
    """Validate the payment webhook shared secret when configured.

    Example: allowed = is_payment_webhook_authorized()
    """
    expected_secret = current_app.config.get("PAYMENT_WEBHOOK_SECRET")
    if not expected_secret:
        return current_app.config.get("APP_ENV") not in {"production", "prod"}
    submitted_secret = request.headers.get("X-Webhook-Secret", "")
    return hmac.compare_digest(expected_secret, submitted_secret)
