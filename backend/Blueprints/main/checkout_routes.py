from flask import Blueprint, jsonify, redirect, url_for
from flask_login import current_user, login_required

checkout_bp = Blueprint("checkout", __name__)
@checkout_bp.route("/checkout")
@login_required
def checkout(): return redirect(url_for("main.planos"))

@checkout_bp.route("/checkout/pro", methods=["POST"])
@login_required
def checkout_pro():
    if current_user.plano == "pro" and current_user.status_assinatura == "active": return jsonify({"checkout_url": url_for("main.planos")})
    return jsonify({"checkout_url": url_for("main.planos")})
