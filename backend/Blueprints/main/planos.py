from flask import Blueprint, current_app, render_template

planos_bp = Blueprint("main", __name__)
@planos_bp.route("/planos")
def planos():
    return render_template(
        "planos.html",
        mercado_pago_public_key=current_app.config.get("MERCADO_PAGO_PUBLIC_KEY", ""),
        mercado_pago_plan_price=current_app.config.get("MERCADO_PAGO_PLAN_PRICE", "19.90"),
    )
