from uuid import uuid4

from flask import Blueprint, render_template

planos_bp = Blueprint("main", __name__)
@planos_bp.route("/planos")
def planos():
    return render_template("planos.html", checkout_idempotency_key=str(uuid4()))
