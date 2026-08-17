from dataclasses import dataclass
from decimal import Decimal

from flask import current_app

PRO_PLAN_CODE = "PRO"


class InvalidPlanError(ValueError):
    pass


@dataclass(frozen=True)
class PaymentPlan:
    code: str
    title: str
    amount: Decimal
    currency: str


def get_payment_plan(code: object) -> PaymentPlan:
    normalized_code = str(code or "").strip().upper()
    if normalized_code != PRO_PLAN_CODE:
        raise InvalidPlanError("Plano de pagamento inválido.")

    return PaymentPlan(
        code=PRO_PLAN_CODE,
        title="BoostConvert PRO mensal",
        amount=Decimal(str(current_app.config["PRO_PLAN_PRICE"])).quantize(
            Decimal("0.01")
        ),
        currency="BRL",
    )
