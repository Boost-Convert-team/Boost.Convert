from __future__ import annotations

from uuid import UUID, uuid4

from Blueprints.services.payments.mercado_pago_gateway import (
    MercadoPagoConfigurationError,
    MercadoPagoRequestError,
    checkout_error_status,
)
from Blueprints.services.payments.plans import get_payment_plan
from Blueprints.services.payments.subscription_service import (
    CheckoutConflictError,
    CheckoutValidationError,
    ProviderDataError,
    SubscriptionNotFoundError,
    cancel_user_subscription,
    create_pro_subscription,
    reconcile_subscription,
    subscription_response,
)
from extensions import db
from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from models import Subscription
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

payments_bp = Blueprint("payments", __name__)


@payments_bp.get("/checkout")
@payments_bp.get("/checkout-pro")
@login_required
def checkout() -> Response:
    plan = get_payment_plan("PRO")
    return render_template(
        "checkout_card.html",
        plan=plan,
        price_display=f"R$ {plan.amount:.2f}".replace(".", ","),
        mercado_pago_public_key=str(
            current_app.config.get("MERCADOPAGO_PUBLIC_KEY") or ""
        ).strip(),
        payer_email=current_user.email,
        payment_idempotency_key=str(uuid4()),
    )


@payments_bp.post("/api/payments/checkout")
@login_required
def create_checkout() -> tuple[Response, int] | Response:
    if not request.is_json:
        return _error("Content-Type application/json é obrigatório.", 415)
    try:
        body = request.get_json()
    except (BadRequest, UnsupportedMediaType):
        return _error("JSON inválido.", 400)
    try:
        subscription = create_pro_subscription(
            current_user,
            body,
            request.headers.get("X-Idempotency-Key"),
            _external_url("payments.payment_return"),
        )
    except CheckoutValidationError as exc:
        return _error(str(exc), 400)
    except CheckoutConflictError as exc:
        return _error(str(exc), 409)
    except MercadoPagoConfigurationError:
        current_app.logger.error(
            "mercadopago_checkout_configuration_missing user_id=%s",
            current_user.id,
        )
        return _error("Pagamento temporariamente indisponível.", 503)
    except MercadoPagoRequestError as exc:
        db.session.rollback()
        _log_gateway_error("mercadopago_subscription_create_failed", exc)
        return _error(
            "Não foi possível processar a assinatura. Tente novamente.",
            checkout_error_status(exc),
        )
    except (ProviderDataError, SQLAlchemyError) as exc:
        db.session.rollback()
        current_app.logger.error(
            "subscription_checkout_failed error_type=%s user_id=%s",
            type(exc).__name__,
            current_user.id,
        )
        return _error("Pagamento temporariamente indisponível.", 503)

    result = subscription_response(subscription)
    result["redirect_url"] = url_for(
        "payments.subscription_status_page",
        attempt_id=subscription.checkout_idempotency_key,
    )
    if not result["ok"]:
        result["error"] = "A assinatura não foi autorizada. Confira os dados."
        return jsonify(result), 422
    return jsonify(result), 201


@payments_bp.get("/assinatura/status")
@login_required
def subscription_status_page() -> Response:
    subscription = _user_subscription(request.args.get("attempt_id"))
    result = subscription_response(subscription)
    return render_template(
        "payment_status.html",
        billing=subscription,
        status_url=url_for(
            "payments.subscription_status",
            attempt_id=subscription.checkout_idempotency_key,
        ),
        approved=result["approved"],
    )


@payments_bp.get("/api/subscriptions/<attempt_id>/status")
@login_required
def subscription_status(attempt_id: str) -> tuple[Response, int]:
    subscription = _user_subscription(attempt_id)
    try:
        reconcile_subscription(subscription)
    except (MercadoPagoRequestError, ProviderDataError) as exc:
        db.session.rollback()
        if isinstance(exc, MercadoPagoRequestError):
            _log_gateway_error("mercadopago_subscription_status_failed", exc)
        return _error("Status temporariamente indisponível.", 503)
    return jsonify(subscription_response(subscription)), 200


@payments_bp.post("/api/subscriptions/cancel")
@login_required
def cancel_subscription() -> tuple[Response, int] | Response:
    try:
        cancel_user_subscription(current_user)
    except SubscriptionNotFoundError as exc:
        return _action_error(str(exc), 404)
    except MercadoPagoConfigurationError:
        return _action_error("Cancelamento temporariamente indisponível.", 503)
    except MercadoPagoRequestError as exc:
        db.session.rollback()
        _log_gateway_error("mercadopago_subscription_cancel_failed", exc)
        return _action_error(
            "Não foi possível cancelar a assinatura. Tente novamente.",
            checkout_error_status(exc),
        )
    except (ProviderDataError, SQLAlchemyError) as exc:
        db.session.rollback()
        current_app.logger.error(
            "subscription_cancel_failed error_type=%s user_id=%s",
            type(exc).__name__,
            current_user.id,
        )
        return _action_error("Cancelamento temporariamente indisponível.", 503)

    if request.is_json or request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": True, "status": "canceled"}), 200
    return redirect(url_for("home.conta", subscription="canceled"), code=303)


@payments_bp.get("/pagamento/retorno")
def payment_return() -> str:
    return render_template(
        "payment_return.html",
        title="Assinatura recebida",
        message=(
            "Estamos confirmando a primeira cobrança com o Mercado Pago. "
            "O acesso PRO será liberado após a confirmação segura."
        ),
        payment_state="pending",
    )


def _user_subscription(attempt_id: object) -> Subscription:
    try:
        key = str(UUID(str(attempt_id or "").strip()))
    except (ValueError, AttributeError):
        abort(404)
    subscription = Subscription.query.filter_by(
        user_id=current_user.id,
        provider="mercado_pago",
        checkout_idempotency_key=key,
        plan="PRO",
    ).first()
    if subscription is None:
        abort(404)
    return subscription


def _error(message: str, status: int) -> tuple[Response, int]:
    return jsonify({"ok": False, "error": message}), status


def _action_error(message: str, status: int) -> tuple[Response, int] | Response:
    if request.is_json or request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": False, "error": message}), status
    return redirect(url_for("home.conta", subscription="error"), code=303)


def _external_url(endpoint: str) -> str:
    base_url = str(current_app.config.get("BASE_URL") or "").rstrip("/")
    path = url_for(endpoint)
    return f"{base_url}{path}" if base_url else url_for(endpoint, _external=True)


def _log_gateway_error(event: str, error: MercadoPagoRequestError) -> None:
    current_app.logger.warning(
        "%s http_status=%s provider_code=%s operation=%s user_id=%s plan=PRO",
        event,
        error.status if error.status is not None else "none",
        error.provider_code,
        error.operation,
        current_user.id,
    )
