from flask import Blueprint, Response, abort, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from Blueprints.services.subscription.mercado_pago_service import (
    MercadoPagoError,
    PROVIDER,
    create_monthly_subscription,
    get_plan_price,
)
from Blueprints.services.subscription.mercado_pago_payments_service import (
    APPROVED_PAYMENT_STATUSES,
    PIX_PAYMENT_METHOD,
    PRO_PLAN_NAME,
    create_pix_payment as create_mercado_pago_pix_payment,
    create_one_time_checkout_preference,
)
from models import Payment

checkout_bp = Blueprint("checkout", __name__)


@checkout_bp.route("/checkout")
@login_required
def checkout() -> Response:
    """Send logged-in users to the local plans page.

    Example: GET /checkout
    """
    return redirect(url_for("main.planos"))


@checkout_bp.get("/checkout-pro")
@login_required
def checkout_pro_choice() -> Response:
    """Display the local payment-method choice without creating a charge."""
    return render_template(
        "checkout_pro.html",
        plan_name=PRO_PLAN_NAME,
        price=format_brl(get_plan_price()),
    )


@checkout_bp.post("/api/payment/pix")
@login_required
def create_pix_payment() -> tuple[Response, int]:
    """Create a pending Pix payment; access remains locked until its webhook."""
    try:
        payment = create_mercado_pago_pix_payment(current_user)
    except MercadoPagoError as exc:
        current_app.logger.warning(
            "mercado_pago_pix_create_failed user_id=%s error=%s",
            getattr(current_user, "id", None),
            exc,
        )
        return jsonify({"ok": False, "error": str(exc)}), 502

    payment["redirect_url"] = url_for(
        "checkout.checkout_pix_page",
        payment_id=payment["payment_id"],
    )
    return jsonify(payment), 201


@checkout_bp.get("/checkout-pix")
@login_required
def checkout_pix_page() -> Response:
    payment = get_user_pix_payment_or_404(request.args.get("payment_id", ""))
    is_confirmed = is_payment_confirmed(payment)
    return render_template(
        "checkout_pix.html",
        payment=payment,
        plan_name=PRO_PLAN_NAME,
        price=format_brl(payment.amount or get_plan_price()),
        is_confirmed=is_confirmed,
    )


@checkout_bp.get("/api/payment/pix/<payment_id>/status")
@login_required
def pix_payment_status(payment_id: str) -> tuple[Response, int]:
    payment = get_user_pix_payment_or_404(payment_id)
    return jsonify(
        {
            "ok": True,
            "payment_id": payment.provider_payment_id,
            "status": payment.status,
            "approved": is_payment_confirmed(payment),
        }
    ), 200


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


@checkout_bp.route("/checkout/pix", methods=["POST"])
@checkout_bp.route("/checkout/debit", methods=["POST"])
@checkout_bp.route("/checkout/pro", methods=["POST"])
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


def get_user_pix_payment_or_404(payment_id: str) -> Payment:
    normalized_id = str(payment_id or "").strip()
    if not normalized_id:
        abort(404)
    payment = Payment.query.filter_by(
        user_id=current_user.id,
        provider=PROVIDER,
        provider_payment_id=normalized_id,
        payment_method=PIX_PAYMENT_METHOD,
    ).first()
    if payment is None:
        abort(404)
    return payment


def format_brl(value: object) -> str:
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def is_payment_confirmed(payment: Payment) -> bool:
    return payment.status.lower() in APPROVED_PAYMENT_STATUSES and payment.premium_expires_at is not None
