from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import stripe
from extensions import db
from flask import current_app
from models import Usuario


class StripeConfigurationError(RuntimeError):
    pass


class StripeCheckoutError(RuntimeError):
    pass


@dataclass(frozen=True)
class CheckoutResult:
    session_id: str
    checkout_url: str


def create_subscription_checkout(usuario: Usuario, success_url: str, cancel_url: str) -> CheckoutResult:
    secret_key = _required_config("STRIPE_SECRET_KEY")
    price_id = _required_config("STRIPE_PRO_PRICE_ID")
    customer_id = _get_or_create_customer(usuario, secret_key)

    try:
        session = stripe.checkout.Session.create(
            api_key=secret_key,
            customer=customer_id,
            client_reference_id=str(usuario.id),
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            metadata={"boostconvert_user_id": str(usuario.id)},
            subscription_data={
                "metadata": {
                    "boostconvert_user_id": str(usuario.id),
                    "boostconvert_plan": "pro",
                }
            },
            success_url=success_url,
            cancel_url=cancel_url,
            idempotency_key=f"checkout-{usuario.id}-{uuid4()}",
        )
    except stripe.StripeError as exc:
        raise StripeCheckoutError("Não foi possível iniciar o pagamento. Tente novamente.") from exc

    session_id = str(_value(session, "id") or "")
    checkout_url = str(_value(session, "url") or "")
    if not session_id or not checkout_url.startswith("https://checkout.stripe.com/"):
        raise StripeCheckoutError("A Stripe não retornou uma sessão de pagamento válida.")
    return CheckoutResult(session_id=session_id, checkout_url=checkout_url)


def _get_or_create_customer(usuario: Usuario, secret_key: str) -> str:
    if usuario.stripe_customer_id:
        return usuario.stripe_customer_id

    try:
        customer = stripe.Customer.create(
            api_key=secret_key,
            email=usuario.email,
            name=usuario.nome or None,
            metadata={"boostconvert_user_id": str(usuario.id)},
            idempotency_key=f"boostconvert-user-{usuario.id}-customer",
        )
    except stripe.StripeError as exc:
        raise StripeCheckoutError("Não foi possível iniciar o pagamento. Tente novamente.") from exc

    customer_id = str(_value(customer, "id") or "")
    if not customer_id.startswith("cus_"):
        raise StripeCheckoutError("A Stripe não retornou um cliente válido.")
    usuario.stripe_customer_id = customer_id
    db.session.commit()
    return customer_id


def _required_config(name: str) -> str:
    value = str(current_app.config.get(name) or "").strip()
    if not value:
        raise StripeConfigurationError(f"{name} não está configurada.")
    return value


def _value(data: object, key: str, default: object = None) -> object:
    if isinstance(data, dict):
        return data.get(key, default)
    return getattr(data, key, default)
