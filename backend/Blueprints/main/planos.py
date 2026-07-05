from flask import Blueprint, render_template

planos_bp = Blueprint("main", __name__)
@planos_bp.route("/planos")
def planos(): return render_template("planos.html")
