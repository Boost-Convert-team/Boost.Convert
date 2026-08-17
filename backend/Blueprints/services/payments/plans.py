from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from flask import current_app

PRO_PLAN_CODE = "PRO"


class InvalidPlanError(ValueError):
    pass


@dataclass(frozen=True)
class PaymentPlan:
    code: str
    item_id: str
    title: str
    description: str
    amount: Decimal
    currency: str
    entitlement_duration: timedelta


def get_payment_plan(code: object) -> PaymentPlan:
    normalized_code = str(code or "").strip().upper()
    if normalized_code != PRO_PLAN_CODE:
        raise InvalidPlanError("Plano de pagamento inválido.")

    return PaymentPlan(
        code=PRO_PLAN_CODE,
        item_id="BOOSTCONVERT_PRO_MONTHLY",
        title="BoostConvert PRO mensal",
        description="Assinatura mensal do BoostConvert PRO",
        amount=Decimal(str(current_app.config["PRO_PLAN_PRICE"])).quantize(
            Decimal("0.01")
        ),
        currency="BRL",
        entitlement_duration=timedelta(
            days=int(current_app.config["PRO_PLAN_DURATION_DAYS"])
        ),
    )
