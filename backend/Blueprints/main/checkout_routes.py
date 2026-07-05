from flask import Blueprint, Response, current_app, jsonify, redirect, request, url_for
from flask_login import current_user, login_required

from Blueprints.services.subscription.mercado_pago_service import (
    MercadoPagoError,
    create_monthly_subscription,
)
from Blueprints.services.subscription.mercado_pago_payments_service import (
    create_debit_card_payment,
    create_pix_payment,
)

checkout_bp = Blueprint("checkout", __name__)


@checkout_bp.route("/checkout")
@login_required
def checkout() -> Response:
    """Send logged-in users to the local plans page.

    Example: GET /checkout
    """
    return redirect(url_for("main.planos"))


@checkout_bp.route("/checkout/credit-subscription", methods=["POST"])
@checkout_bp.route("/checkout/pro", methods=["POST"])
@login_required
def checkout_credit_subscription() -> tuple[Response, int]:
    """Create a Mercado Pago monthly subscription for the logged-in user.

    Example: POST /checkout/credit-subscription
    """
    try:
        subscription = create_monthly_subscription(current_user)
    except MercadoPagoError as exc:
        current_app.logger.warning(
            "mercado_pago_subscription_create_failed user_id=%s error=%s",
            getattr(current_user, "id", None),
            exc,
        )
        return jsonify({"ok": False, "error": str(exc)}), 502

    return jsonify(
        {
            "ok": True,
            "provider": "mercado_pago",
            "plan_name": subscription["plan_name"],
            "checkout_url": subscription["checkout_url"],
            "subscription_id": subscription["subscription_id"],
            "status": subscription["status"],
        }
    ), 200


@checkout_bp.route("/checkout/pix", methods=["POST"])
@login_required
def checkout_pix() -> tuple[Response, int]:
    """Create a one-time Pix payment for 30 days of BoostConvert PRO."""
    try:
        payment = create_pix_payment(current_user)
    except MercadoPagoError as exc:
        current_app.logger.warning(
            "mercado_pago_pix_create_failed user_id=%s error=%s",
            getattr(current_user, "id", None),
            exc,
        )
        return jsonify({"ok": False, "error": str(exc)}), 502

    return jsonify(payment), 200


@checkout_bp.route("/checkout/debit", methods=["POST"])
@login_required
def checkout_debit() -> tuple[Response, int]:
    """Create a one-time debit card payment for 30 days of BoostConvert PRO."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "invalid_json"}), 400

    try:
        payment = create_debit_card_payment(current_user, payload)
    except MercadoPagoError as exc:
        current_app.logger.warning(
            "mercado_pago_debit_create_failed user_id=%s error=%s",
            getattr(current_user, "id", None),
            exc,
        )
        return jsonify({"ok": False, "error": str(exc)}), 502

    return jsonify(payment), 200
