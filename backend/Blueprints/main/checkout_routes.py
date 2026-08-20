from __future__ import annotations

from uuid import UUID, uuid4

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
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from Blueprints.services.payments.mercado_pago_client import (
    MercadoPagoConfigurationError,
    MercadoPagoError,
)
from Blueprints.services.payments.payment_service import (
    CardPaymentValidationError,
    CheckoutConflictError,
    InvalidIdempotencyKeyError,
    ProviderPaymentValidationError,
    SubscriptionNotFoundError,
    build_card_payment_response,
    build_card_subscription_response,
    cancel_current_subscription,
    create_card_subscription,
    reconcile_payment,
    reconcile_subscription,
)
from Blueprints.services.payments.plans import (
    PRO_SUBSCRIPTION_MAX_INSTALLMENTS,
    get_payment_plan,
)
from extensions import db
from models import Payment, Subscription

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
        mercado_pago_max_installments=min(
            max(int(current_app.config.get("MERCADOPAGO_MAX_INSTALLMENTS", 1)), 1),
            PRO_SUBSCRIPTION_MAX_INSTALLMENTS,
        ),
        payer_email=current_user.email,
        payment_idempotency_key=str(uuid4()),
    )


@payments_bp.post("/api/payments/checkout")
@login_required
def create_checkout() -> tuple[Response, int] | Response:
    if not request.is_json:
        return _checkout_error("Content-Type application/json é obrigatório.", 415)
    try:
        body = request.get_json()
    except (BadRequest, UnsupportedMediaType):
        return _checkout_error("JSON inválido.", 400)
    idempotency_key = request.headers.get("X-Idempotency-Key")
    try:
        subscription = create_card_subscription(
            current_user,
            body,
            idempotency_key,
            _external_url("payments.payment_return"),
        )
    except (InvalidIdempotencyKeyError, CardPaymentValidationError) as exc:
        return _checkout_error(str(exc), 400)
    except CheckoutConflictError as exc:
        return _checkout_error(
            str(exc), 409, code=exc.code, can_replace=exc.can_replace
        )
    except MercadoPagoConfigurationError:
        current_app.logger.error(
            "subscription_checkout_configuration_missing user_id=%s", current_user.id
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
            "Não foi possível processar o pagamento. Tente novamente.", 502
        )
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error(
            "subscription_checkout_database_failed error_type=%s", type(exc).__name__
        )
        return _checkout_error("Pagamento temporariamente indisponível.", 503)

    result = build_card_subscription_response(subscription)
    result["redirect_url"] = url_for(
        "payments.subscription_status_page",
        attempt_id=subscription.checkout_idempotency_key,
    )
    if subscription.status in {"canceled", "error"}:
        result["error"] = "Pagamento recusado. Confira os dados e tente novamente."
        return jsonify(result), 422
    return jsonify(result), 201 if result["approved"] else 202


@payments_bp.get("/pagamento/status")
@login_required
def payment_status_page() -> Response:
    payment = get_user_payment_or_404(request.args.get("attempt_id"))
    return render_template(
        "payment_status.html",
        billing=payment,
        status_url=url_for("payments.payment_status", attempt_id=payment.attempt_id),
        approved=payment.status == "approved"
        and payment.premium_expires_at is not None,
    )


@payments_bp.get("/api/payments/<attempt_id>/status")
@login_required
def payment_status(attempt_id: str) -> tuple[Response, int]:
    payment = get_user_payment_or_404(attempt_id)
    try:
        reconcile_payment(payment)
    except ProviderPaymentValidationError:
        db.session.rollback()
        return _checkout_error("Não foi possível validar o pagamento.", 502)
    except MercadoPagoError as exc:
        db.session.rollback()
        _log_mercado_pago_error(
            "mercadopago_payment_status_failed",
            exc,
            user_id=current_user.id,
        )
        return _checkout_error("Status temporariamente indisponível.", 503)
    return jsonify(build_card_payment_response(payment)), 200


@payments_bp.get("/assinatura/status")
@login_required
def subscription_status_page() -> Response:
    subscription = get_user_subscription_or_404(request.args.get("attempt_id"))
    result = build_card_subscription_response(subscription)
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
    subscription = get_user_subscription_or_404(attempt_id)
    try:
        reconcile_subscription(subscription)
    except MercadoPagoError as exc:
        db.session.rollback()
        _log_mercado_pago_error(
            "mercadopago_subscription_status_failed",
            exc,
            user_id=current_user.id,
            plan="PRO",
        )
        return _checkout_error("Status temporariamente indisponível.", 503)
    return jsonify(build_card_subscription_response(subscription)), 200


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
        "Pagamento recebido",
        "Estamos confirmando o pagamento com o Mercado Pago. O acesso PRO só será liberado após a confirmação segura.",
        "pending",
    )


def _render_payment_return(title: str, message: str, state: str) -> str:
    return render_template(
        "payment_return.html", title=title, message=message, payment_state=state
    )


def _checkout_error(
    message: str,
    status: int,
    *,
    code: str | None = None,
    can_replace: bool = False,
) -> tuple[Response, int] | Response:
    if request.is_json or request.accept_mimetypes.best == "application/json":
        payload: dict[str, object] = {"ok": False, "error": message}
        if code:
            payload["code"] = code
        if can_replace:
            payload["can_replace"] = True
        return jsonify(payload), status
    return redirect(url_for("main.planos", checkout="error"), code=303)


def get_user_payment_or_404(attempt_id: object) -> Payment:
    try:
        normalized_attempt_id = str(UUID(str(attempt_id or "").strip()))
    except (ValueError, AttributeError):
        abort(404)
    payment = Payment.query.filter_by(
        user_id=current_user.id,
        provider="mercado_pago",
        attempt_id=normalized_attempt_id,
        payment_method="credit_card",
    ).first()
    if payment is None:
        abort(404)
    return payment


def get_user_subscription_or_404(attempt_id: object) -> Subscription:
    try:
        normalized_attempt_id = str(UUID(str(attempt_id or "").strip()))
    except (ValueError, AttributeError):
        abort(404)
    subscription = Subscription.query.filter_by(
        user_id=current_user.id,
        provider="mercado_pago",
        checkout_idempotency_key=normalized_attempt_id,
        plan="PRO",
    ).first()
    if subscription is None:
        abort(404)
    return subscription


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
        "%s status=%s operation=%s endpoint=%s provider_code=%s user_id=%s plan=%s",
        event,
        error.status if error.status is not None else "none",
        error.operation,
        error.endpoint,
        error.provider_code,
        user_id,
        plan or "none",
    )
