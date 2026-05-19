from flask import Blueprint, render_template
from flask_login import current_user

planos_bp = Blueprint("main",__name__)

@planos_bp.route("/planos")
def planos():
    return render_template("planos.html", usuario=current_user)