from flask import Blueprint, Response, current_app, jsonify, redirect, url_for
from flask_login import current_user, login_required

from Blueprints.services.subscription.mercado_pago_service import (
    MercadoPagoError,
    create_monthly_subscription,
)

checkout_bp = Blueprint("checkout", __name__)


@checkout_bp.route("/checkout")
@login_required
def checkout() -> Response:
    """Send logged-in users to the local plans page.

    Example: GET /checkout
    """
    return redirect(url_for("main.planos"))


@checkout_bp.route("/checkout/pro", methods=["POST"])
@login_required
def checkout_pro() -> tuple[Response, int]:
    """Create a Mercado Pago monthly subscription for the logged-in user.

    Example: POST /checkout/pro
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
            "checkout_url": subscription["checkout_url"],
            "subscription_id": subscription["subscription_id"],
            "status": subscription["status"],
        }
    ), 200
