from flask import Blueprint, Response, redirect
from flask_login import login_required

checkout_bp = Blueprint("checkout", __name__)
KIWIFY_CHECKOUT_URL = "https://pay.kiwify.com.br/pOcJvQr"


@checkout_bp.route("/checkout")
@login_required
def checkout() -> Response:
    """Redirect logged-in users to the Kiwify checkout.

    Example: GET /checkout
    """
    return redirect(KIWIFY_CHECKOUT_URL)


@checkout_bp.route("/checkout/pro", methods=["POST"])
@login_required
def checkout_pro() -> Response:
    """Redirect logged-in users to the Kiwify PRO checkout.

    Example: POST /checkout/pro
    """
    return redirect(KIWIFY_CHECKOUT_URL)
