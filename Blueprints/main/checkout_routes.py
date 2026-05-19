from flask import Blueprint, jsonify, redirect, url_for
from flask_login import login_required, current_user
from extensions import db
from Blueprints.services.subscription.payment_service import create_payment_preference

checkout_bp = Blueprint("checkout", __name__)


@checkout_bp.route("/checkout/pro", methods=["POST"])
@login_required
def create_checkout():
    preference = create_payment_preference(current_user)

    return jsonify(preference), 200


@checkout_bp.route("/simulate/pro-payment")
@login_required
def simulate_pro_payment():
    current_user.plano = "pro"
    current_user.status_assinatura = "active"

    db.session.commit()

    return redirect(url_for("main.planos"))