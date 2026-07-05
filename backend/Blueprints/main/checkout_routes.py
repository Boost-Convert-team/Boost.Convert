from flask import Blueprint, Response, current_app, jsonify, redirect, url_for
from flask_login import current_user, login_required

from Blueprints.services.subscription.mercado_pago_service import (
    MercadoPagoError,
    create_monthly_subscription,
)
from Blueprints.services.subscription.mercado_pago_payments_service import (
    create_one_time_checkout_preference,
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


@checkout_bp.route("/checkout/pro", methods=["POST"])
@checkout_bp.route("/checkout/pix", methods=["POST"])
@checkout_bp.route("/checkout/debit", methods=["POST"])
@login_required
def checkout_pro() -> tuple[Response, int]:
    """Create a Checkout Pro preference for 30 days of BoostConvert PRO."""
    try:
        checkout = create_one_time_checkout_preference(current_user)
    except MercadoPagoError as exc:
        current_app.logger.warning(
            "mercado_pago_checkout_preference_create_failed user_id=%s error=%s",
            getattr(current_user, "id", None),
            exc,
        )
        return jsonify({"ok": False, "error": str(exc)}), 502

    return jsonify(checkout), 200
