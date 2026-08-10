from __future__ import annotations

from Blueprints.services.subscription.stripe_checkout_service import (
    StripeCheckoutError,
    StripeConfigurationError,
    create_subscription_checkout,
)
from extensions import db
from flask import Blueprint, Response, current_app, jsonify, redirect, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

checkout_bp = Blueprint("checkout", __name__)


@checkout_bp.get("/checkout")
@checkout_bp.get("/checkout-pro")
@login_required
def checkout() -> Response:
    return redirect(url_for("main.planos"))


@checkout_bp.post("/api/billing/checkout")
@login_required
def create_checkout_session() -> tuple[Response, int] | Response:
    try:
        result = create_subscription_checkout(
            current_user,
            _external_url("main.planos", checkout="success"),
            _external_url("main.planos", checkout="canceled"),
        )
    except StripeConfigurationError:
        current_app.logger.error("stripe_checkout_configuration_missing user_id=%s", current_user.id)
        return _checkout_error("Pagamento temporariamente indisponível.", 503)
    except StripeCheckoutError as exc:
        db.session.rollback()
        current_app.logger.warning("stripe_checkout_failed user_id=%s", current_user.id)
        return _checkout_error(str(exc), 502)
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error("stripe_checkout_database_failed error_type=%s", type(exc).__name__)
        return _checkout_error("Pagamento temporariamente indisponível.", 503)

    if request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": True, "checkout_url": result.checkout_url}), 201
    return redirect(result.checkout_url, code=303)


def _checkout_error(message: str, status: int) -> tuple[Response, int] | Response:
    if request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": False, "error": message}), status
    return redirect(url_for("main.planos", checkout="error"), code=303)


def _external_url(endpoint: str, **values: str) -> str:
    base_url = str(current_app.config.get("BASE_URL") or "").rstrip("/")
    path = url_for(endpoint, **values)
    return f"{base_url}{path}" if base_url else url_for(endpoint, _external=True, **values)
