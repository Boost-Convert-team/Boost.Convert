from flask import Blueprint, request, redirect, url_for
from models import Usuario
from extensions import db

webhook_bp = Blueprint("webhook", __name__)

@webhook_bp.route("/webhook/payment", methods=["POST"])
def payment_webhook():
    user_id = request.form.get("user_id")
    event = request.form.get("event")

    if event == "payment_approved":
        usuario = Usuario.query.get(user_id)

        if usuario:
            usuario.plano = "pro"
            usuario.status_assinatura = "active"
            db.session.commit()

    return redirect(url_for("main.planos"))