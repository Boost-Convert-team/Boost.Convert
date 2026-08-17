from __future__ import annotations

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from Blueprints.services.payments.mercado_pago_client import (
    MercadoPagoConfigurationError,
    MercadoPagoError,
)
from Blueprints.services.payments.payment_service import (
    CheckoutConflictError,
    InvalidIdempotencyKeyError,
    SubscriptionNotFoundError,
    cancel_current_subscription,
    create_subscription_checkout,
)
from Blueprints.services.payments.plans import InvalidPlanError
from extensions import db

payments_bp = Blueprint("payments", __name__)


@payments_bp.get("/checkout")
@payments_bp.get("/checkout-pro")
@login_required
def checkout() -> Response:
    return redirect(url_for("main.planos"))


@payments_bp.post("/api/payments/checkout")
@login_required
def create_checkout() -> tuple[Response, int] | Response:
    body = request.get_json(silent=True) if request.is_json else request.form
    plan = (body or {}).get("plan_id")
    idempotency_key = request.headers.get("X-Idempotency-Key") or (body or {}).get(
        "idempotency_key"
    )
    try:
        result = create_subscription_checkout(
            current_user,
            plan,
            idempotency_key,
            _external_url("payments.payment_return"),
        )
    except (InvalidPlanError, InvalidIdempotencyKeyError) as exc:
        return _checkout_error(str(exc), 400)
    except CheckoutConflictError as exc:
        return _checkout_error(str(exc), 409)
    except MercadoPagoConfigurationError:
        current_app.logger.error(
            "payment_checkout_configuration_missing user_id=%s", current_user.id
        )
        return _checkout_error("Pagamento temporariamente indisponível.", 503)
    except MercadoPagoError as exc:
        db.session.rollback()
        _log_mercado_pago_error(
            "mercadopago_subscription_create_failed",
            exc,
            user_id=current_user.id,
            plan="PRO",
        )
        return _checkout_error(
            "Não foi possível iniciar sua assinatura. Tente novamente.", 502
        )
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error(
            "payment_checkout_database_failed error_type=%s", type(exc).__name__
        )
        return _checkout_error("Pagamento temporariamente indisponível.", 503)

    if request.is_json or request.accept_mimetypes.best == "application/json":
        status = 200 if result.reused else 201
        return jsonify({"checkout_url": result.checkout_url}), status
    return redirect(result.checkout_url, code=303)


@payments_bp.post("/api/subscriptions/cancel")
@login_required
def cancel_subscription() -> tuple[Response, int] | Response:
    try:
        cancel_current_subscription(current_user)
    except SubscriptionNotFoundError as exc:
        return _subscription_action_error(str(exc), 404)
    except MercadoPagoConfigurationError:
        current_app.logger.error(
            "subscription_cancel_configuration_missing user_id=%s", current_user.id
        )
        return _subscription_action_error(
            "Cancelamento temporariamente indisponível.", 503
        )
    except MercadoPagoError as exc:
        db.session.rollback()
        _log_mercado_pago_error(
            "mercadopago_subscription_cancel_failed",
            exc,
            user_id=current_user.id,
        )
        return _subscription_action_error(
            "Não foi possível cancelar a assinatura. Tente novamente.", 502
        )
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error(
            "subscription_cancel_database_failed error_type=%s", type(exc).__name__
        )
        return _subscription_action_error(
            "Cancelamento temporariamente indisponível.", 503
        )

    current_app.logger.info("subscription_cancelled user_id=%s", current_user.id)
    if request.is_json or request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": True, "status": "canceled"}), 200
    return redirect(url_for("home.conta", subscription="canceled"), code=303)


@payments_bp.get("/pagamento/retorno")
def payment_return() -> str:
    return _render_payment_return(
        "Assinatura recebida",
        "Estamos confirmando sua assinatura com o Mercado Pago. O acesso PRO só será liberado após a confirmação segura da cobrança.",
        "pending",
    )


def _render_payment_return(title: str, message: str, state: str) -> str:
    return render_template(
        "payment_return.html", title=title, message=message, payment_state=state
    )


def _checkout_error(message: str, status: int) -> tuple[Response, int] | Response:
    if request.is_json or request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": False, "error": message}), status
    return redirect(url_for("main.planos", checkout="error"), code=303)


def _subscription_action_error(
    message: str, status: int
) -> tuple[Response, int] | Response:
    if request.is_json or request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": False, "error": message}), status
    return redirect(url_for("home.conta", subscription="error"), code=303)


def _external_url(endpoint: str) -> str:
    base_url = str(current_app.config.get("BASE_URL") or "").rstrip("/")
    path = url_for(endpoint)
    return f"{base_url}{path}" if base_url else url_for(endpoint, _external=True)


def _log_mercado_pago_error(
    event: str,
    error: MercadoPagoError,
    *,
    user_id: int,
    plan: str | None = None,
) -> None:
    current_app.logger.warning(
        "%s status=%s operation=%s endpoint=%s provider_code=%s "
        "provider_message=%s user_id=%s plan=%s",
        event,
        error.status if error.status is not None else "none",
        error.operation,
        error.endpoint,
        error.provider_code,
        error.provider_message,
        user_id,
        plan or "none",
    )
