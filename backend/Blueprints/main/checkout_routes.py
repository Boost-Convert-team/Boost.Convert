from uuid import UUID, uuid4

from Blueprints.services.subscription.mercado_pago_payments_service import (
    APPROVED_PAYMENT_STATUSES,
    PIX_PAYMENT_METHOD,
    PRO_PLAN_NAME,
    CardPaymentValidationError,
    IdempotencyKeyValidationError,
    get_payment_attempt_id,
    reconcile_payment,
)
from Blueprints.services.subscription.mercado_pago_payments_service import (
    create_card_payment as create_mercado_pago_card_payment,
)
from Blueprints.services.subscription.mercado_pago_payments_service import (
    create_pix_payment as create_mercado_pago_pix_payment,
)
from Blueprints.services.subscription.mercado_pago_service import (
    PROVIDER,
    MercadoPagoConfigurationError,
    MercadoPagoError,
    MercadoPagoHTTPError,
    MercadoPagoInvalidResponseError,
    MercadoPagoTimeoutError,
    create_monthly_subscription,
    get_plan_price,
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
from models import Payment
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

checkout_bp = Blueprint("checkout", __name__)


@checkout_bp.route("/checkout")
@login_required
def checkout() -> Response:
    return redirect(url_for("main.planos"))


@checkout_bp.get("/checkout-pro")
@login_required
def checkout_pro_choice() -> Response:
    """Display the card and PIX one-time payment flows."""

    return render_template(
        "checkout_pro.html",
        plan_name=PRO_PLAN_NAME,
        price=format_brl(get_plan_price()),
        price_amount=f"{get_plan_price():.2f}",
        mercado_pago_public_key=current_app.config.get("MERCADO_PAGO_PUBLIC_KEY") or "",
        mercado_pago_max_installments=int(
            current_app.config.get("MERCADO_PAGO_MAX_INSTALLMENTS", 12)
        ),
        payer_email=current_user.email,
        pix_idempotency_key=str(uuid4()),
        card_idempotency_key=str(uuid4()),
    )


@checkout_bp.post("/api/payment/pix")
@login_required
def create_pix_payment() -> tuple[Response, int]:
    try:
        payment = create_mercado_pago_pix_payment(
            current_user,
            request.form.get("pix_idempotency_key")
            or request.headers.get("X-Idempotency-Key"),
        )
    except IdempotencyKeyValidationError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except SQLAlchemyError as exc:
        return handle_payment_database_error("pix_create", exc)
    except MercadoPagoError as exc:
        return handle_provider_error("pix_create", exc)

    payment["redirect_url"] = url_for(
        "checkout.checkout_pix_page",
        payment_id=payment["payment_id"],
    )
    return jsonify(payment), 201 if payment.get("approved") else 202


@checkout_bp.post("/api/payment/card")
@login_required
def create_card_payment() -> tuple[Response, int]:
    """Accept only Card Payment Brick tokenized JSON for a one-time charge."""
    if not request.is_json:
        return jsonify(
            {"ok": False, "error": "Content-Type application/json e obrigatorio."}
        ), 415

    try:
        payload = request.get_json()
    except (BadRequest, UnsupportedMediaType):
        return jsonify({"ok": False, "error": "JSON invalido."}), 400

    try:
        payment = create_mercado_pago_card_payment(
            current_user,
            payload,
            request.headers.get("X-Idempotency-Key"),
        )
    except IdempotencyKeyValidationError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except CardPaymentValidationError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 422
    except SQLAlchemyError as exc:
        return handle_payment_database_error("card_create", exc)
    except MercadoPagoError as exc:
        return handle_provider_error("card_create", exc)

    payment["redirect_url"] = url_for(
        "checkout.checkout_card_status_page",
        attempt_id=payment["attempt_id"],
    )

    status = str(payment.get("status") or "").lower()

    if status in {"rejected", "cancelled", "canceled"}:
        payment["ok"] = False
        payment["error"] = get_card_status_message(
            str(payment.get("status_detail") or "")
        )
        return jsonify(payment), 422

    return jsonify(payment), 201 if payment.get("approved") else 202


@checkout_bp.get("/checkout-card/status")
@login_required
def checkout_card_status_page() -> Response:
    payment = get_user_card_attempt_or_404(request.args.get("attempt_id", ""))

    return render_template(
        "checkout_card_status.html",
        payment=payment,
        plan_name=PRO_PLAN_NAME,
        price=format_brl(payment.amount or get_plan_price()),
        is_confirmed=is_payment_confirmed(payment),
    )


@checkout_bp.get("/checkout-pix")
@login_required
def checkout_pix_page() -> Response:
    payment = get_user_pix_payment_or_404(request.args.get("payment_id", ""))
    return render_template(
        "checkout_pix.html",
        payment=payment,
        plan_name=PRO_PLAN_NAME,
        price=format_brl(payment.amount or get_plan_price()),
        is_confirmed=is_payment_confirmed(payment),
    )


@checkout_bp.get("/api/payment/pix/<payment_id>/status")
@login_required
def pix_payment_status(payment_id: str) -> tuple[Response, int]:
    payment = get_user_pix_payment_or_404(payment_id)
    return build_reconciled_status_response(payment, "pix_status")


@checkout_bp.get("/api/payment/card/<attempt_id>/status")
@login_required
def card_payment_status(attempt_id: str) -> tuple[Response, int]:

    payment = get_user_card_attempt_or_404(attempt_id)
    return build_reconciled_status_response(payment, "card_status")


@checkout_bp.post("/checkout/credit-subscription")
@login_required
def checkout_credit_subscription() -> tuple[Response, int]:
    """Create the original Mercado Pago monthly subscription."""
    try:
        subscription = create_monthly_subscription(current_user)
    except MercadoPagoError as exc:
        current_app.logger.warning(
            "mercado_pago_subscription_create_failed user_id=%s error_type=%s",
            getattr(current_user, "id", None),
            type(exc).__name__,
        )
        return jsonify({"ok": False, "error": str(exc)}), 502

    return jsonify(
        {
            "ok": True,
            "provider": "mercado_pago",
            "plan_name": subscription["plan_name"],
            "checkout_url": subscription["checkout_url"],
            "subscription_id": subscription["subscription_id"],
            "status": subscription["status"],
        }
    ), 200


@checkout_bp.post("/checkout/debit")
@checkout_bp.post("/checkout/pix")
@checkout_bp.post("/checkout/pro")
@login_required
def legacy_checkout_disabled() -> tuple[Response, int]:
    """Keep obsolete hosted-checkout endpoints out of the current payment UI."""
    return jsonify(
        {
            "ok": False,
            "error": "Checkout antigo desativado. Use o cartao de credito ou debito no checkout atual.",
            "checkout_url": url_for("checkout.checkout_pro_choice"),
        }
    ), 410


def build_reconciled_status_response(
    payment: Payment,
    operation: str,
) -> tuple[Response, int]:

    try:
        payment = reconcile_payment(payment)
    except SQLAlchemyError as exc:
        return handle_payment_database_error(operation, exc)
    except MercadoPagoError as exc:
        return handle_provider_error(operation, exc)
    return jsonify(
        {
            "ok": True,
            "attempt_id": get_payment_attempt_id(payment),
            "payment_id": payment.provider_payment_id,
            "status": payment.status,
            "status_detail": payment.status_detail,
            "payment_method_id": payment.provider_payment_method_id,
            "payment_type_id": payment.payment_type_id,
            "approved": is_payment_confirmed(payment),
        }
    ), 200


def get_user_card_attempt_or_404(attempt_id: str) -> Payment:
    try:
        normalized_attempt_id = str(UUID(str(attempt_id).strip()))
    except (ValueError, AttributeError):
        abort(404)

    payment = (
        Payment.query.filter_by(
            user_id=current_user.id,
            provider=PROVIDER,
            idempotency_key=normalized_attempt_id,
        )
        .filter(
            Payment.payment_method.in_({"credit_card", "debit_card", "pending_card"})
        )
        .first()
    )

    if payment is None:
        abort(404)

    return payment


def get_user_pix_payment_or_404(payment_id: str) -> Payment:
    normalized_id = str(payment_id or "").strip()
    if not normalized_id or len(normalized_id) > 120:
        abort(404)
    payment = Payment.query.filter_by(
        user_id=current_user.id,
        provider=PROVIDER,
        provider_payment_id=normalized_id,
        payment_method=PIX_PAYMENT_METHOD,
    ).first()
    if payment is None:
        abort(404)
    return payment


def handle_payment_database_error(
    operation: str,
    exc: SQLAlchemyError,
) -> tuple[Response, int]:

    db.session.rollback()

    current_app.logger.exception(
        "PAYMENT DATABASE ERROR REAL operation=%s error_type=%s",
        operation,
        type(exc).__name__,
    )

    return jsonify(
        {
            "ok": False,
            "error": "Pagamentos temporariamente indisponiveis. Tente novamente em instantes.",
        }
    ), 503


def handle_provider_error(
    operation: str,
    exc: MercadoPagoError,
) -> tuple[Response, int]:
    db.session.rollback()
    current_app.logger.warning(
        "payment_error status=%s code=%s cause=%s correlation_id=%s",
        getattr(exc, "provider_status", "local"),
        getattr(exc, "code", "payment_error"),
        getattr(exc, "cause", type(exc).__name__),
        getattr(exc, "correlation_id", "unavailable"),
    )

    if isinstance(exc, MercadoPagoHTTPError):
        response = jsonify(
            {
                "ok": False,
                "error": str(exc),
                "provider_status": exc.provider_status,
                "code": exc.provider_code,
                "cause": exc.provider_cause,
                "correlation_id": exc.correlation_id,
            }
        )
        if exc.retry_after:
            response.headers["Retry-After"] = exc.retry_after

        return response, exc.public_status

    if isinstance(exc, MercadoPagoTimeoutError):
        return jsonify(build_safe_payment_error(exc)), 503
    if isinstance(exc, MercadoPagoInvalidResponseError):
        return jsonify(build_safe_payment_error(exc)), 502
    if isinstance(exc, MercadoPagoConfigurationError):
        return jsonify(build_safe_payment_error(exc)), 503

    return jsonify(
        {"ok": False, "error": "Nao foi possivel processar o pagamento."}
    ), 502


def build_safe_payment_error(exc: MercadoPagoError) -> dict[str, object]:
    return {
        "ok": False,
        "error": str(exc),
        "code": exc.code,
        "cause": exc.cause,
        "correlation_id": exc.correlation_id,
    }


def get_card_status_message(status_detail: str) -> str:
    messages = {
        "cc_rejected_bad_filled_card_number": "Confira o numero do cartao e tente novamente.",
        "cc_rejected_bad_filled_date": "Confira a validade do cartao e tente novamente.",
        "cc_rejected_bad_filled_security_code": "Confira o codigo de seguranca e tente novamente.",
        "cc_rejected_insufficient_amount": "O cartao nao possui limite ou saldo suficiente.",
        "cc_rejected_card_disabled": "O cartao esta desabilitado. Fale com o banco emissor.",
        "cc_rejected_call_for_authorize": "O banco emissor precisa autorizar este pagamento.",
        "cc_rejected_duplicated_payment": "Este pagamento ja foi processado.",
        "cc_rejected_max_attempts": "O limite de tentativas foi atingido. Use outro cartao.",
        "cc_rejected_high_risk": "O pagamento nao foi autorizado. Use outro meio de pagamento.",
    }
    return messages.get(
        status_detail.lower(),
        "Pagamento recusado. Revise os dados ou use outro cartao.",
    )


def format_brl(value: object) -> str:
    return (
        f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )


def is_payment_confirmed(payment: Payment) -> bool:
    return (
        payment.status.lower() in APPROVED_PAYMENT_STATUSES
        and payment.premium_expires_at is not None
    )
