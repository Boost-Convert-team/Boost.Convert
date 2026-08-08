from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse
from uuid import UUID

from Blueprints.services.subscription.mercado_pago_service import (
    PRO_PLAN_CODE,
    PROVIDER,
    MercadoPagoConfigurationError,
    MercadoPagoError,
    build_payment_external_reference,
    extract_payment_attempt_id,
    extract_user_id_from_external_reference,
    get_base_url,
    get_plan_price,
    get_string,
    mercado_pago_request,
    parse_decimal,
    parse_provider_datetime,
    utc_now,
)
from Blueprints.services.subscription.subscription_service import (
    APPROVED_PAYMENT_STATUSES,
    as_utc,
    synchronize_user_pro_status,
)
from extensions import db
from flask import current_app
from models import Payment, Subscription, Usuario
from sqlalchemy.exc import IntegrityError

PRO_PLAN_NAME = "BoostConvert PRO"
PROVIDER_PRO_PLAN_CODE = "pro"
ONE_TIME_ACCESS_DAYS = 30
ALLOWED_CARD_PAYMENT_TYPES = {
    "credit_card",
    "debit_card",
}
ALLOWED_ONE_TIME_PAYMENT_KINDS = ALLOWED_CARD_PAYMENT_TYPES
FAILED_PAYMENT_STATUSES = {
    "cancelled",
    "canceled",
    "rejected",
    "expired",
    "refunded",
    "charged_back",
}
CREATING_PAYMENT_STATUS = "creating"
CARD_REQUEST_KEYS = {
    "token",
    "payment_method_id",
    "payment_type_id",
    "issuer_id",
    "installments",
    "payer",
}
IGNORED_CLIENT_PAYMENT_KEYS = {"transaction_amount"}
CARD_PAYER_KEYS = {"email", "identification"}
CARD_IDENTIFICATION_KEYS = {"type", "number"}


class CardPaymentValidationError(MercadoPagoError):
    """A card request failed local, non-sensitive validation."""


class IdempotencyKeyValidationError(CardPaymentValidationError):
    """The card idempotency key is absent or not a UUID."""


def create_card_payment(
    usuario: Usuario,
    card_data: dict[str, Any],
    idempotency_key: str | None,
) -> dict[str, Any]:
    """Create a card payment using a short-lived browser token."""
    require_payment_environment()
    normalized_key = normalize_idempotency_key(idempotency_key)
    validated = validate_card_request(card_data, usuario)

    get_card_payment_method(
        validated["payment_method_id"],
        validated["payment_type_id"],
    )

    payment = get_or_create_payment_attempt(usuario, normalized_key)
    bind_card_request_to_attempt(payment, validated)
    log_payment_attempt_started(payment)
    if payment.provider_payment_id:
        return build_card_payment_response(payment)

    recovered = recover_provider_payment_for_attempt(payment)
    if recovered is not None and recovered.provider_payment_id:
        return build_card_payment_response(recovered)

    payer: dict[str, Any] = {"email": validated["payer"]["email"]}
    identification = validated["payer"].get("identification")

    if identification:
        payer["identification"] = identification

    # The token exists only in this local payload. It is never assigned to a
    # model and is deliberately absent from every application log.
    payload = {
        "token": validated["token"],
        "transaction_amount": float(get_expected_payment_amount(payment)),
        "description": f"{PRO_PLAN_NAME} - 30 dias",
        "installments": validated["installments"],
        "payment_method_id": validated["payment_method_id"],
        "payer": payer,
        "external_reference": payment.external_reference,
        "notification_url": get_payment_notification_url(),
        "metadata": build_payment_metadata(payment),
        "statement_descriptor": "BOOSTCONVERT",
    }

    if validated["issuer_id"]:
        payload["issuer_id"] = validated["issuer_id"]
    log_payment_request(
        payment,
        payment_method_id=validated["payment_method_id"],
        payment_type_id=validated["payment_type_id"],
        installments=validated["installments"],
    )
    data = mercado_pago_request(
        "POST",
        "/v1/payments",
        json_payload=payload,
        extra_headers={"X-Idempotency-Key": normalized_key},
    )

    validate_provider_environment(data)
    payment = upsert_payment_from_provider_data(
        data,
        user=usuario,
        requested_payment_method_id=validated["payment_method_id"],
        requested_payment_type_id=validated["payment_type_id"],
        activate_access=True,
        existing_payment=payment,
    )

    db.session.commit()

    log_payment_event("mercado_pago_card_payment_created", payment)
    return build_card_payment_response(payment)


def validate_card_request(card_data: object, usuario: Usuario) -> dict[str, Any]:

    if not isinstance(card_data, dict):
        raise CardPaymentValidationError("Envie os dados do cartao em JSON.")
    unexpected = set(card_data) - CARD_REQUEST_KEYS - IGNORED_CLIENT_PAYMENT_KEYS

    if unexpected:
        raise CardPaymentValidationError("O pagamento contem campos nao permitidos.")

    token = normalize_limited_string(card_data.get("token"), "token", 2048)
    method_id = normalize_limited_string(
        card_data.get("payment_method_id"), "payment_method_id", 50
    ).lower()
    payment_type_id = normalize_limited_string(
        card_data.get("payment_type_id"), "payment_type_id", 50
    ).lower()
    if payment_type_id not in ALLOWED_CARD_PAYMENT_TYPES:
        raise CardPaymentValidationError(
            "O tipo do cartao deve ser credito ou debito conforme identificado pelo Mercado Pago."
        )

    issuer_id = str(card_data.get("issuer_id") or "").strip()
    if len(issuer_id) > 50:
        raise CardPaymentValidationError("Campo issuer_id invalido.")

    try:
        installments = int(card_data.get("installments"))
    except (TypeError, ValueError):
        installments = 0

    max_installments = int(
        current_app.config.get("MERCADO_PAGO_MAX_INSTALLMENTS") or 12
    )
    if installments < 1 or installments > max_installments:
        raise CardPaymentValidationError("Quantidade de parcelas invalida.")
    if payment_type_id == "debit_card" and installments != 1:
        raise CardPaymentValidationError(
            "Cartao de debito deve ser pago em uma parcela."
        )

    payer_data = card_data.get("payer")
    if not isinstance(payer_data, dict) or set(payer_data) - CARD_PAYER_KEYS:
        raise CardPaymentValidationError("Dados do pagador invalidos.")

    email = normalize_limited_string(
        payer_data.get("email"), "payer.email", 200
    ).lower()
    if email != str(usuario.email).strip().lower():
        raise CardPaymentValidationError(
            "O email do pagador nao corresponde ao usuario."
        )

    payer: dict[str, Any] = {"email": email}
    identification = payer_data.get("identification")
    if identification not in (None, {}):
        if (
            not isinstance(identification, dict)
            or set(identification) - CARD_IDENTIFICATION_KEYS
        ):
            raise CardPaymentValidationError("Identificacao do pagador invalida.")

        payer["identification"] = {
            "type": normalize_limited_string(
                identification.get("type"), "payer.identification.type", 10
            ),
            "number": normalize_limited_string(
                identification.get("number"), "payer.identification.number", 30
            ),
        }

    return {
        "token": token,
        "payment_method_id": method_id,
        "payment_type_id": payment_type_id,
        "issuer_id": issuer_id,
        "installments": installments,
        "payer": payer,
    }


def normalize_limited_string(value: object, field: str, max_length: int) -> str:
    normalized = str(value or "").strip()

    if not normalized or len(normalized) > max_length:
        raise CardPaymentValidationError(f"Campo {field} invalido.")

    return normalized


def mask_identifier(value: str) -> str:
    return f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "[masked]"


def log_payment_request(
    payment: Payment,
    *,
    payment_method_id: str,
    payment_type_id: str | None = None,
    installments: int | None = None,
) -> None:
    current_app.logger.info(
        json.dumps(
            {
                "event": "MERCADO_PAGO_REQUEST",
                "internal_payment_id": payment.id,
                "external_reference": payment.external_reference,
                "user_id": payment.user_id,
                "plan_id": payment.plan,
                "amount": f"{get_expected_payment_amount(payment):.2f}",
                "environment": current_app.config.get("MERCADO_PAGO_ENVIRONMENT"),
                "payment_method_id": payment_method_id,
                "payment_type_id": payment_type_id,
                "installments": installments,
                "idempotency_key": mask_identifier(payment.idempotency_key or ""),
            },
            ensure_ascii=False,
        )
    )


def log_payment_attempt_started(payment: Payment) -> None:
    current_app.logger.info(
        json.dumps(
            {
                "event": "PAYMENT_ATTEMPT_STARTED",
                "internal_payment_id": payment.id,
                "external_reference": payment.external_reference,
                "user_id": payment.user_id,
                "plan_id": payment.plan,
                "amount": f"{get_expected_payment_amount(payment):.2f}",
                "environment": current_app.config.get("MERCADO_PAGO_ENVIRONMENT"),
                "payment_method_id": payment.provider_payment_method_id,
                "payment_type_id": payment.payment_type_id,
                "installments": payment.installments,
                "idempotency_key": mask_identifier(payment.idempotency_key or ""),
            },
            ensure_ascii=False,
        )
    )


def get_card_payment_method(
    payment_method_id: str,
    payment_type_id: str,
) -> dict[str, Any]:
    methods = mercado_pago_request(
        "GET",
        "/v1/payment_methods",
        expected_response_types=(list,),
    )

    method = next(
        (
            item
            for item in methods
            if isinstance(item, dict)
            and get_string(item, "id").lower() == payment_method_id.lower()
            and get_string(item, "payment_type_id").lower() == payment_type_id.lower()
        ),
        None,
    )

    if method is None:
        raise CardPaymentValidationError(
            "Bandeira e tipo do cartao nao correspondem a um meio de pagamento disponivel."
        )
    if get_string(method, "status").lower() not in {"active", ""}:
        raise CardPaymentValidationError(
            "O meio de pagamento selecionado esta indisponivel."
        )
    return method


def get_or_create_payment_attempt(
    usuario: Usuario,
    idempotency_key: str,
    *,
    payment_method: str = "pending_card",
) -> Payment:
    payment = Payment.query.filter_by(
        provider=PROVIDER,
        idempotency_key=idempotency_key,
    ).first()

    if payment is not None:
        validate_attempt_owner(payment, usuario)
        return payment

    payment = Payment(
        user_id=usuario.id,
        provider=PROVIDER,
        external_reference=build_payment_external_reference(
            usuario.id, idempotency_key
        ),
        plan=PRO_PLAN_CODE,
        idempotency_key=idempotency_key,
        payment_method=payment_method,
        provider_payment_method_id=None,
        status=CREATING_PAYMENT_STATUS,
        amount=get_plan_price(),
        currency="BRL",
    )

    db.session.add(payment)

    try:
        db.session.commit()
        return payment
    except IntegrityError:
        current_app.logger.exception("mercado_pago_payment_attempt_integrity_conflict")

        db.session.rollback()
        payment = Payment.query.filter_by(
            provider=PROVIDER,
            idempotency_key=idempotency_key,
        ).first()

        if payment is None:
            raise MercadoPagoError("Nao foi possivel iniciar o pagamento.")

        validate_attempt_owner(payment, usuario)
        return payment


def bind_card_request_to_attempt(
    payment: Payment,
    validated: dict[str, Any],
) -> None:
    """Persist the non-sensitive card contract before contacting the provider."""
    requested_type = validated["payment_type_id"]
    requested_method = validated["payment_method_id"]
    if payment.payment_type_id and payment.payment_type_id != requested_type:
        raise CardPaymentValidationError(
            "Esta tentativa ja foi iniciada com outro tipo de cartao."
        )
    if (
        payment.provider_payment_method_id
        and payment.provider_payment_method_id != requested_method
    ):
        raise CardPaymentValidationError(
            "Esta tentativa ja foi iniciada com outro meio de pagamento."
        )
    if payment.installments and payment.installments != validated["installments"]:
        raise CardPaymentValidationError(
            "Esta tentativa ja foi iniciada com outra quantidade de parcelas."
        )
    payment.payment_method = requested_type
    payment.payment_type_id = requested_type
    payment.provider_payment_method_id = requested_method
    payment.installments = validated["installments"]
    db.session.commit()


def validate_attempt_owner(
    payment: Payment,
    usuario: Usuario,
) -> None:
    if payment.user_id != usuario.id:
        raise MercadoPagoError("Chave de idempotencia pertence a outro pagamento.")


def normalize_idempotency_key(value: str | None) -> str:
    if value:
        try:
            return str(UUID(str(value).strip()))
        except (ValueError, AttributeError):
            pass

    raise IdempotencyKeyValidationError("X-Idempotency-Key UUID e obrigatorio.")


def recover_provider_payment_for_attempt(payment: Payment) -> Payment | None:
    if payment.provider_payment_id:
        return payment

    data = search_payment_by_external_reference(payment.external_reference)
    if data is None:
        return None

    recovered = upsert_payment_from_provider_data(
        data,
        user=payment.user,
        requested_payment_method_id=payment.provider_payment_method_id,
        requested_payment_type_id=(
            payment.payment_type_id
            if payment.payment_method in ALLOWED_CARD_PAYMENT_TYPES
            else None
        ),
        activate_access=False,
        existing_payment=payment,
    )
    db.session.commit()
    return recovered


def search_payment_by_external_reference(
    external_reference: str | None,
) -> dict[str, Any] | None:
    if not external_reference:
        return None

    query = urlencode(
        {
            "external_reference": external_reference,
            "sort": "date_created",
            "criteria": "desc",
            "limit": "10",
        }
    )

    result = mercado_pago_request("GET", f"/v1/payments/search?{query}")
    if not isinstance(result, dict):
        raise MercadoPagoError("Busca de pagamento retornou dados invalidos.")
    entries = result.get("results")

    if not isinstance(entries, list):
        raise MercadoPagoError("Busca de pagamento retornou dados invalidos.")

    matches = [
        item
        for item in entries
        if isinstance(item, dict)
        and get_string(item, "external_reference") == external_reference
    ]

    if len(matches) > 1:
        current_app.logger.error(
            "mercado_pago_duplicate_external_reference attempt_id=%s count=%s",
            extract_payment_attempt_id(external_reference),
            len(matches),
        )

        raise MercadoPagoError("Referencia externa duplicada no Mercado Pago.")

    return matches[0] if matches else None


def get_payment(payment_id: str) -> dict[str, Any]:
    normalized_id = str(payment_id or "").strip()

    if not normalized_id or len(normalized_id) > 120:
        raise MercadoPagoError("ID de pagamento invalido.")

    return mercado_pago_request("GET", f"/v1/payments/{normalized_id}")


def process_confirmed_payment(payment_id: str) -> Payment:
    data = get_payment(payment_id)
    return upsert_payment_from_provider_data(data, activate_access=True)


def reconcile_payment(payment: Payment, *, force: bool = False) -> Payment:
    """Refresh a pending local attempt, throttled and reusable by status routes."""
    payment = (
        Payment.query.filter_by(id=payment.id).with_for_update().first() or payment
    )

    if is_payment_locally_final(payment):
        return payment

    now = utc_now()
    minimum_interval = max(
        1, int(current_app.config.get("MERCADO_PAGO_RECONCILE_INTERVAL_SECONDS", 10))
    )

    sync_times = current_app.extensions.setdefault(
        "mercado_pago_reconcile_last_sync", {}
    )

    sync_key = f"{payment.provider}:{payment.id}"
    last_sync = as_utc(sync_times.get(sync_key))

    if (
        not force
        and last_sync
        and now - last_sync < timedelta(seconds=minimum_interval)
    ):
        return payment

    sync_times[sync_key] = now

    if payment.provider_payment_id:
        data = get_payment(payment.provider_payment_id)
    else:
        data = search_payment_by_external_reference(payment.external_reference)

        if data is None:
            return payment

    payment = upsert_payment_from_provider_data(
        data,
        user=payment.user,
        requested_payment_method_id=payment.provider_payment_method_id,
        requested_payment_type_id=(
            payment.payment_type_id
            if payment.payment_method in ALLOWED_CARD_PAYMENT_TYPES
            else None
        ),
        activate_access=True,
        existing_payment=payment,
    )
    db.session.commit()
    return payment


def upsert_payment_from_provider_data(
    provider_data: dict[str, Any],
    user: Usuario | None = None,
    requested_payment_method_id: str | None = None,
    requested_payment_type_id: str | None = None,
    activate_access: bool = False,
    existing_payment: Payment | None = None,
) -> Payment:
    provider_payment_id = get_string(provider_data, "id")
    if not provider_payment_id:
        raise MercadoPagoError("Pagamento do Mercado Pago sem ID.")

    provider_payment = Payment.query.filter_by(
        provider=PROVIDER,
        provider_payment_id=provider_payment_id,
    ).first()

    if (
        provider_payment is not None
        and existing_payment is not None
        and provider_payment.id != existing_payment.id
    ):
        raise MercadoPagoError("Pagamento ja vinculado a outra tentativa.")

    attempt_id = extract_payment_attempt_id(provider_data.get("external_reference"))
    attempt_payment = None

    if attempt_id:
        attempt_payment = Payment.query.filter_by(
            provider=PROVIDER,
            idempotency_key=attempt_id,
        ).first()

    candidates = {
        item.id
        for item in (provider_payment, existing_payment, attempt_payment)
        if item is not None and item.id is not None
    }

    if len(candidates) > 1:
        raise MercadoPagoError("Correlacao do pagamento diverge da tentativa.")

    payment = provider_payment or existing_payment or attempt_payment
    external_user_id = extract_user_id_from_external_reference(
        provider_data.get("external_reference")
    )

    if payment is not None:
        validate_provider_identity(payment, provider_data, external_user_id)

    if (
        user is not None
        and external_user_id is not None
        and user.id != external_user_id
    ):
        raise MercadoPagoError("Referencia externa nao corresponde ao usuario.")

    user = user or find_user_for_payment(provider_data, payment)
    if user is None:
        raise MercadoPagoError("Usuario do pagamento nao encontrado.")

    if payment is None:
        # One-time payments must originate from a persisted local attempt. This
        # prevents an arbitrary valid Mercado Pago payment from granting access.
        if not get_string(provider_data, "preapproval_id"):
            raise MercadoPagoError("Tentativa local do pagamento nao encontrada.")

        payment = Payment(
            user_id=user.id,
            provider=PROVIDER,
            provider_payment_id=provider_payment_id,
            payment_method=detect_payment_type(provider_data),
        )
        db.session.add(payment)

    elif (
        payment.provider_payment_id
        and payment.provider_payment_id != provider_payment_id
    ):
        raise MercadoPagoError("Tentativa ja vinculada a outro pagamento.")

    previous_payment_type = payment.payment_method
    detected_payment_type = detect_payment_type(provider_data)
    provider_payment_type_id = get_string(provider_data, "payment_type_id").lower()
    detected_payment_method_id = get_string(provider_data, "payment_method_id").lower()

    if requested_payment_type_id and detected_payment_type != requested_payment_type_id:
        raise MercadoPagoError("Tipo retornado diverge do cartao solicitado.")
    if (
        requested_payment_method_id
        and detected_payment_method_id != requested_payment_method_id
    ):
        raise MercadoPagoError("Bandeira retornada diverge do cartao solicitado.")

    if activate_access:
        validate_provider_environment(provider_data)
        if detected_payment_type not in ALLOWED_ONE_TIME_PAYMENT_KINDS:
            raise MercadoPagoError("Metodo de pagamento nao pode conceder acesso PRO.")

        if not get_string(provider_data, "preapproval_id"):
            validate_one_time_provider_contract(
                payment,
                provider_data,
                detected_payment_type,
                previous_payment_type,
            )

    payment.user_id = user.id
    payment.user = user
    payment.provider_payment_id = provider_payment_id
    payment.provider_subscription_id = (
        get_string(provider_data, "preapproval_id") or payment.provider_subscription_id
    )

    payment.external_reference = (
        get_string(provider_data, "external_reference") or payment.external_reference
    )

    payment.plan = payment.plan or get_provider_plan(provider_data) or PRO_PLAN_CODE
    payment.status = get_string(provider_data, "status") or "pending"
    payment.status_detail = get_string(provider_data, "status_detail") or None
    payment.provider_payment_method_id = (
        detected_payment_method_id or payment.provider_payment_method_id
    )
    payment.payment_type_id = provider_payment_type_id or payment.payment_type_id
    if detected_payment_type:
        payment.payment_method = detected_payment_type
    provider_installments = provider_data.get("installments")
    if provider_installments is not None:
        try:
            payment.installments = int(provider_installments)
        except (TypeError, ValueError):
            raise MercadoPagoError(
                "Parcelas retornadas pelo Mercado Pago sao invalidas."
            )

    if payment.amount is None:
        payment.amount = parse_decimal(provider_data.get("transaction_amount"))

    payment.currency = (
        payment.currency or get_string(provider_data, "currency_id") or "BRL"
    )
    payment.payment_created_at = (
        parse_provider_datetime(provider_data.get("date_created"))
        or payment.payment_created_at
    )

    payment.updated_at = utc_now()
    payment.last_provider_sync_at = utc_now()

    if activate_access:
        apply_confirmed_payment_status(
            payment,
            provider_data,
            previous_payment_method=previous_payment_type,
        )

    return payment


def validate_provider_identity(
    payment: Payment,
    provider_data: dict[str, Any],
    external_user_id: int | None,
) -> None:

    provider_reference = get_string(provider_data, "external_reference")
    if not provider_reference or provider_reference != payment.external_reference:
        raise MercadoPagoError("Referencia externa nao corresponde a tentativa salva.")

    if external_user_id is not None and payment.user_id != external_user_id:
        raise MercadoPagoError("Referencia externa nao corresponde ao pagamento salvo.")

    attempt_id = extract_payment_attempt_id(provider_reference)
    local_attempt_id = get_payment_attempt_id(payment)

    if attempt_id is not None and attempt_id != local_attempt_id:
        raise MercadoPagoError("UUID da tentativa nao corresponde ao pagamento salvo.")

    metadata_attempt = get_provider_attempt_id(provider_data)
    metadata_user_id = get_provider_user_id(provider_data)

    if attempt_id is not None:
        if metadata_attempt != local_attempt_id:
            raise MercadoPagoError("UUID dos metadados nao corresponde a tentativa.")

        if metadata_user_id != payment.user_id:
            raise MercadoPagoError("Usuario dos metadados nao corresponde a tentativa.")

    elif metadata_attempt and metadata_attempt != local_attempt_id:
        raise MercadoPagoError("UUID dos metadados nao corresponde a tentativa.")


def require_payment_environment() -> str:
    app_environment = str(current_app.config.get("APP_ENV") or "development").lower()
    access_token = str(
        current_app.config.get("MERCADO_PAGO_ACCESS_TOKEN") or ""
    ).strip()
    public_key = str(current_app.config.get("MERCADO_PAGO_PUBLIC_KEY") or "").strip()
    environment = str(current_app.config.get("MERCADO_PAGO_ENVIRONMENT") or "").lower()

    if (
        not environment
        and app_environment not in {"production", "prod"}
        and access_token.startswith("TEST-")
        and public_key.startswith("TEST-")
    ):
        environment = "test"

    if environment not in {"test", "production"}:
        raise MercadoPagoConfigurationError(
            "MERCADO_PAGO_ENVIRONMENT deve ser test ou production.",
            code="payment_environment_not_configured",
        )

    if not access_token:
        raise MercadoPagoConfigurationError(
            "MERCADO_PAGO_ACCESS_TOKEN nao configurado.",
            code="payment_access_token_missing",
        )

    if environment == "test" and not access_token.startswith("TEST-"):
        raise MercadoPagoConfigurationError(
            "Ambiente de teste exige credencial TEST.",
            code="payment_test_credential_invalid",
        )

    if environment == "test" and public_key and not public_key.startswith("TEST-"):
        raise MercadoPagoConfigurationError(
            "Ambiente de teste exige chave publica TEST.",
            code="payment_test_public_key_invalid",
        )

    if environment == "production" and access_token.startswith("TEST-"):
        raise MercadoPagoConfigurationError(
            "Credencial TEST nao pode processar pagamento de producao.",
            code="payment_production_credential_invalid",
        )

    if environment == "production" and public_key.startswith("TEST-"):
        raise MercadoPagoConfigurationError(
            "Chave publica TEST nao pode ser usada em producao.",
            code="payment_production_public_key_invalid",
        )

    if environment == "production" and app_environment not in {"production", "prod"}:
        raise MercadoPagoConfigurationError(
            "Pagamento real bloqueado fora do ambiente de producao.",
            code="production_payment_blocked",
        )

    if (
        environment == "production"
        and not str(current_app.config.get("MERCADO_PAGO_COLLECTOR_ID") or "").strip()
    ):
        raise MercadoPagoConfigurationError(
            "MERCADO_PAGO_COLLECTOR_ID nao configurado.",
            code="payment_collector_missing",
        )

    notification_url = get_payment_notification_url()
    parsed_notification_url = urlparse(notification_url)

    is_local_test_url = (
        app_environment not in {"production", "prod"}
        and parsed_notification_url.scheme == "http"
        and parsed_notification_url.hostname in {"localhost", "127.0.0.1", "::1"}
    )

    if not parsed_notification_url.netloc or (
        parsed_notification_url.scheme != "https" and not is_local_test_url
    ):
        raise MercadoPagoConfigurationError(
            "BASE_URL HTTPS e obrigatoria para notificacoes de pagamento.",
            code="payment_notification_url_invalid",
        )
    return environment


def validate_provider_environment(provider_data: dict[str, Any]) -> None:
    environment = require_payment_environment()
    expected_live_mode = environment == "production"
    if provider_data.get("live_mode") is not expected_live_mode:
        raise MercadoPagoError("Ambiente do pagamento nao corresponde a aplicacao.")

    expected_collector_id = str(
        current_app.config.get("MERCADO_PAGO_COLLECTOR_ID") or ""
    ).strip()

    collector_id = str(provider_data.get("collector_id") or "").strip()

    if expected_collector_id and collector_id != expected_collector_id:
        raise MercadoPagoError("Recebedor do pagamento nao corresponde a aplicacao.")

    if not expected_collector_id and environment == "production":
        raise MercadoPagoConfigurationError(
            "MERCADO_PAGO_COLLECTOR_ID nao configurado.",
            code="payment_collector_missing",
        )


def apply_confirmed_payment_status(
    payment: Payment,
    provider_data: dict[str, Any],
    previous_payment_method: str,
) -> None:
    status = payment.status.lower()
    detected_method = detect_payment_type(provider_data)
    subscription = get_payment_subscription(payment)

    if subscription is not None:
        subscription.latest_payment_status = status
        subscription.provider_payment_id = payment.provider_payment_id

    if status in APPROVED_PAYMENT_STATUSES:
        payment.payment_method = detected_method
        payment.approved_at = (
            parse_provider_datetime(provider_data.get("date_approved"))
            or payment.approved_at
            or utc_now()
        )

        paid_through_at = get_payment_paid_through_at(subscription, payment.approved_at)
        current_expiry = as_utc(payment.premium_expires_at)

        if current_expiry is None or current_expiry < paid_through_at:
            payment.premium_expires_at = paid_through_at

        if subscription is not None:
            current_paid_through = as_utc(subscription.paid_through_at)

            if current_paid_through is None or current_paid_through < paid_through_at:
                subscription.paid_through_at = paid_through_at

    # A refund/chargeback removes this record from active-access queries while
    # preserving access granted by any other still-valid payment.
    synchronize_user_pro_status(payment.user, persist=False)


def validate_one_time_provider_contract(
    payment: Payment,
    provider_data: dict[str, Any],
    detected_method: str,
    previous_payment_method: str,
) -> None:

    if detected_method not in ALLOWED_ONE_TIME_PAYMENT_KINDS:
        raise MercadoPagoError("Metodo de pagamento invalido para o plano PRO.")
    if previous_payment_method not in {"", "pending_card", detected_method}:
        raise MercadoPagoError(
            "Tipo do pagamento confirmado diverge da tentativa salva."
        )
    provider_method_id = get_string(provider_data, "payment_method_id").lower()
    if not provider_method_id or (
        payment.provider_payment_method_id
        and provider_method_id != payment.provider_payment_method_id
    ):
        raise MercadoPagoError(
            "Bandeira do pagamento confirmado diverge da tentativa salva."
        )
    if detected_method == "debit_card":
        try:
            provider_installments = int(
                provider_data.get("installments", payment.installments)
            )
        except (TypeError, ValueError) as exc:
            raise MercadoPagoError(
                "Parcelas do pagamento de debito sao invalidas."
            ) from exc
        if provider_installments != 1:
            raise MercadoPagoError("Pagamento de debito nao pode ser parcelado.")

    provider_reference = get_string(
        provider_data,
        "external_reference",
    )

    if provider_reference != payment.external_reference:
        raise MercadoPagoError("Referencia externa do pagamento invalida.")

    amount = parse_decimal(provider_data.get("transaction_amount"))

    if amount is None or amount != get_expected_payment_amount(payment):
        raise MercadoPagoError("Valor do pagamento nao corresponde ao plano PRO.")

    currency = get_string(
        provider_data,
        "currency_id",
    ).upper()

    if currency != "BRL":
        raise MercadoPagoError("Moeda do pagamento nao corresponde ao plano PRO.")

    provider_plan = get_provider_plan(provider_data)

    if provider_plan not in {
        PRO_PLAN_CODE,
        PROVIDER_PRO_PLAN_CODE,
    }:
        raise MercadoPagoError(
            "Plano do pagamento nao corresponde ao BoostConvert PRO."
        )


def get_expected_payment_amount(payment: Payment) -> Decimal:
    if payment.amount is not None:
        return Decimal(payment.amount).quantize(Decimal("0.01"))

    if payment.provider_subscription_id:
        subscription = get_payment_subscription(payment)
        if subscription is not None and subscription.amount is not None:
            return Decimal(subscription.amount).quantize(Decimal("0.01"))
    return get_plan_price()


def get_payment_subscription(payment: Payment) -> Subscription | None:
    if not payment.provider_subscription_id:
        return None

    return Subscription.query.filter_by(
        provider=PROVIDER,
        provider_subscription_id=payment.provider_subscription_id,
    ).first()


def get_payment_paid_through_at(
    subscription: Subscription | None,
    approved_at: datetime,
) -> datetime:
    if subscription is not None:
        next_payment_at = as_utc(subscription.next_payment_at)

        if next_payment_at is not None and next_payment_at > approved_at:
            return next_payment_at
    return approved_at + timedelta(days=ONE_TIME_ACCESS_DAYS)


def find_user_for_payment(
    provider_data: dict[str, Any],
    payment: Payment | None,
) -> Usuario | None:
    user_id = extract_user_id_from_external_reference(
        provider_data.get("external_reference")
    )
    if payment is not None and user_id is not None and payment.user_id != user_id:
        return None

    if user_id is not None:
        return db.session.get(Usuario, user_id)

    if payment is not None:
        return payment.user

    preapproval_id = get_string(provider_data, "preapproval_id")
    if preapproval_id:
        subscription = Subscription.query.filter_by(
            provider=PROVIDER,
            provider_subscription_id=preapproval_id,
        ).first()

        if subscription is not None:
            return subscription.user
    return None


def detect_payment_type(provider_data: dict[str, Any]) -> str:
    payment_type_id = get_string(provider_data, "payment_type_id")
    return payment_type_id.lower()


def get_provider_plan(provider_data: dict[str, Any]) -> str:
    metadata = provider_data.get("metadata")
    if not isinstance(metadata, dict):
        return ""
    return get_string(metadata, "plan")


def get_provider_attempt_id(provider_data: dict[str, Any]) -> str:
    metadata = provider_data.get("metadata")
    if not isinstance(metadata, dict):
        return ""

    value = get_string(metadata, "attempt_id")
    if not value:
        return ""

    try:
        return str(UUID(value))
    except (ValueError, AttributeError):
        return "invalid"


def get_provider_user_id(provider_data: dict[str, Any]) -> int | None:
    metadata = provider_data.get("metadata")
    if not isinstance(metadata, dict):
        return None

    try:
        return int(metadata.get("user_id"))
    except (TypeError, ValueError):
        return None


def build_payment_metadata(payment: Payment) -> dict[str, Any]:
    return {
        "user_id": payment.user_id,
        "plan": PROVIDER_PRO_PLAN_CODE,
        "attempt_id": get_payment_attempt_id(payment),
        "payment_method": payment.payment_method,
    }


def get_payment_attempt_id(payment: Payment) -> str:
    try:
        return str(UUID(str(payment.idempotency_key or "").strip()))
    except (ValueError, AttributeError):
        return ""


def get_payment_notification_url() -> str:
    return urljoin(f"{get_base_url()}/", "api/webhooks/mercadopago")


def build_card_payment_response(payment: Payment) -> dict[str, Any]:
    amount = payment.amount or get_plan_price()
    return {
        "ok": True,
        "provider": PROVIDER,
        "plan": payment.plan or PRO_PLAN_CODE,
        "plan_name": PRO_PLAN_NAME,
        "attempt_id": get_payment_attempt_id(payment),
        "payment_id": payment.provider_payment_id,
        "status": payment.status,
        "status_detail": payment.status_detail,
        "payment_method_id": payment.provider_payment_method_id,
        "payment_type_id": payment.payment_type_id,
        "installments": payment.installments,
        "approved": (
            payment.status.lower() in APPROVED_PAYMENT_STATUSES
            and payment.premium_expires_at is not None
        ),
        "amount": f"{amount:.2f}",
    }


def log_payment_event(event: str, payment: Payment) -> None:
    current_app.logger.info(
        json.dumps(
            {
                "event": event,
                "user_id": payment.user_id,
                "attempt_id": get_payment_attempt_id(payment),
                "provider_payment_id": payment.provider_payment_id,
                "payment_method_id": payment.provider_payment_method_id,
                "payment_type_id": payment.payment_type_id,
                "installments": payment.installments,
                "status": payment.status,
                "status_detail": payment.status_detail,
            },
            ensure_ascii=False,
        )
    )


def is_payment_locally_final(payment: Payment) -> bool:
    status = payment.status.lower()
    if status in APPROVED_PAYMENT_STATUSES:
        return payment.premium_expires_at is not None
    return status in FAILED_PAYMENT_STATUSES
