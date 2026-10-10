from flask import Blueprint, render_template
from flask_login import current_user

from Blueprints.services.access.access_service import FREE_PLAN, PRO_PLAN, is_pro_user
from Blueprints.services.convertions_services.conversion_rules.conversion_limits import get_plan_limits

PRO_MONTHLY_PRICE = "25,90"

planos_bp = Blueprint("main", __name__)


def build_pricing_context() -> dict[str, object]:
    """Plan cards on the home and pricing pages, from the limits the uploads enforce."""
    limits = get_plan_limits()
    return {
        "free": limits[FREE_PLAN],
        "pro": limits[PRO_PLAN],
        "pro_price": PRO_MONTHLY_PRICE,
        "is_pro": is_pro_user(current_user),
    }


@planos_bp.route("/planos")
def planos():
    return render_template("planos.html", **build_pricing_context())
