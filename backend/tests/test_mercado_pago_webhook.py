import hashlib
import hmac
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from werkzeug.test import TestResponse

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.main.webhook_routes import webhook_bp
from Blueprints.services.subscription.mercado_pago_service import build_webhook_manifest
from extensions import db
from models import Payment, PaymentWebhookEvent, Subscription, Usuario


WEBHOOK_SECRET = "test-mercado-pago-webhook-secret"


def _serialize_payload(payload: dict[str, object]) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


class MercadoPagoWebhookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            APP_ENV="production",
            MERCADO_PAGO_ACCESS_TOKEN="TEST-token",
            MERCADO_PAGO_WEBHOOK_SECRET=WEBHOOK_SECRET,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.app.register_blueprint(webhook_bp)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

    def tearDown(self) -> None:
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_authorized_subscription_without_approved_invoice_stays_free(self) -> None:
        user_id = self.create_user("cliente@example.com", "free", "inactive")
        provider_data = self.provider_subscription_data(user_id, "sub_123", "authorized")

        with patch(
            "Blueprints.services.subscription.mercado_pago_service.get_subscription",
            return_value=provider_data,
        ):
            response = self.post_mercado_pago_payload(
                {"id": 1001, "type": "subscription_preapproval", "data": {"id": "sub_123"}},
                "sub_123",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user_plan_state(user_id), ("free", "inactive"))
        self.assertEqual(self.subscription_status("sub_123"), "authorized")
        self.assertEqual(
            self.subscription_payment_state("sub_123"),
            (None, None),
        )
        self.assertEqual(self.webhook_event_count(), 1)

    def test_canceled_subscription_sets_user_plan_to_free(self) -> None:
        user_id = self.create_user("cliente-pro@example.com", "pro", "active")
        provider_data = self.provider_subscription_data(user_id, "sub_456", "canceled")

        with patch(
            "Blueprints.services.subscription.mercado_pago_service.get_subscription",
            return_value=provider_data,
        ):
            response = self.post_mercado_pago_payload(
                {"id": 1002, "type": "subscription_preapproval", "data": {"id": "sub_456"}},
                "sub_456",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user_plan_state(user_id), ("free", "inactive"))
        self.assertEqual(self.subscription_status("sub_456"), "canceled")

    def test_canceled_subscription_preserves_already_paid_period(self) -> None:
        paid_through_at = datetime.now(timezone.utc) + timedelta(days=10)
        user_id = self.create_user("cancelado-pago@example.com", "pro", "active")
        self.create_existing_paid_subscription(
            user_id,
            "sub_cancelled_paid",
            "pay_cancelled_paid_period",
            paid_through_at,
        )
        provider_data = self.provider_subscription_data(
            user_id,
            "sub_cancelled_paid",
            "canceled",
        )

        with patch(
            "Blueprints.services.subscription.mercado_pago_service.get_subscription",
            return_value=provider_data,
        ):
            response = self.post_mercado_pago_payload(
                {
                    "id": 1007,
                    "type": "subscription_preapproval",
                    "data": {"id": "sub_cancelled_paid"},
                },
                "sub_cancelled_paid",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.subscription_status("sub_cancelled_paid"), "canceled")
        self.assertEqual(self.user_plan_state(user_id), ("pro", "active"))

    def test_duplicate_event_is_not_processed_again(self) -> None:
        user_id = self.create_user("duplicado@example.com", "free", "inactive")
        provider_data = self.provider_subscription_data(user_id, "sub_dup", "authorized")
        payload = {"id": 1003, "type": "subscription_preapproval", "data": {"id": "sub_dup"}}

        with patch(
            "Blueprints.services.subscription.mercado_pago_service.get_subscription",
            return_value=provider_data,
        ) as get_subscription:
            first_response = self.post_mercado_pago_payload(payload, "sub_dup")
            second_response = self.post_mercado_pago_payload(payload, "sub_dup")

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertTrue(second_response.json["duplicate"])
        self.assertEqual(get_subscription.call_count, 1)
        self.assertEqual(self.webhook_event_count(), 1)

    def test_approved_recurring_invoice_activates_until_next_charge(self) -> None:
        user_id = self.create_user("recorrente-aprovado@example.com", "free", "inactive")
        subscription_data = self.provider_subscription_data(
            user_id,
            "sub_recurring_paid",
            "authorized",
        )
        payment_data = self.provider_payment_data(
            user_id,
            "pay_recurring_paid",
            "approved",
            "visa",
            "credit_card",
        )
        payment_data["preapproval_id"] = "sub_recurring_paid"
        invoice_data = {
            "id": "invoice_paid",
            "preapproval_id": "sub_recurring_paid",
            "status": "processed",
            "payment": {"id": "pay_recurring_paid", "status": "approved"},
        }

        with patch(
            "Blueprints.services.subscription.mercado_pago_service.get_authorized_payment",
            return_value=invoice_data,
        ), patch(
            "Blueprints.services.subscription.mercado_pago_service.get_subscription",
            return_value=subscription_data,
        ), patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
            return_value=payment_data,
        ):
            response = self.post_mercado_pago_payload(
                {
                    "id": 1004,
                    "type": "subscription_authorized_payment",
                    "data": {"id": "invoice_paid"},
                },
                "invoice_paid",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user_plan_state(user_id), ("pro", "active"))
        payment_status, paid_through_at = self.subscription_payment_state(
            "sub_recurring_paid"
        )
        self.assertEqual(payment_status, "approved")
        self.assertEqual(
            paid_through_at.replace(tzinfo=timezone.utc),
            datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
        self.assertEqual(self.payment_state("pay_recurring_paid")[1], "approved")

    def test_processed_invoice_without_payment_id_does_not_activate_pro(self) -> None:
        user_id = self.create_user("fatura-sem-pagamento@example.com", "free", "inactive")
        subscription_data = self.provider_subscription_data(
            user_id,
            "sub_invoice_without_payment",
            "authorized",
        )
        invoice_data = {
            "id": "invoice_without_payment",
            "preapproval_id": "sub_invoice_without_payment",
            "status": "processed",
        }

        with patch(
            "Blueprints.services.subscription.mercado_pago_service.get_authorized_payment",
            return_value=invoice_data,
        ), patch(
            "Blueprints.services.subscription.mercado_pago_service.get_subscription",
            return_value=subscription_data,
        ), patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
        ) as get_payment:
            response = self.post_mercado_pago_payload(
                {
                    "id": 1008,
                    "type": "subscription_authorized_payment",
                    "data": {"id": "invoice_without_payment"},
                },
                "invoice_without_payment",
            )

        self.assertEqual(response.status_code, 200)
        get_payment.assert_not_called()
        self.assertEqual(self.user_plan_state(user_id), ("free", "inactive"))
        self.assertEqual(
            self.subscription_payment_state("sub_invoice_without_payment"),
            ("pending", None),
        )

    def test_rejected_renewal_preserves_already_paid_period(self) -> None:
        paid_through_at = datetime.now(timezone.utc) + timedelta(days=10)
        user_id = self.create_user("recorrente-recusado@example.com", "pro", "active")
        self.create_existing_paid_subscription(
            user_id,
            "sub_recurring_rejected",
            "pay_previous_period",
            paid_through_at,
        )
        subscription_data = self.provider_subscription_data(
            user_id,
            "sub_recurring_rejected",
            "authorized",
        )
        payment_data = self.provider_payment_data(
            user_id,
            "pay_rejected_renewal",
            "rejected",
            "visa",
            "credit_card",
        )
        payment_data["preapproval_id"] = "sub_recurring_rejected"
        invoice_data = {
            "id": "invoice_rejected",
            "preapproval_id": "sub_recurring_rejected",
            "status": "recycling",
            "payment": {"id": "pay_rejected_renewal", "status": "rejected"},
        }

        with patch(
            "Blueprints.services.subscription.mercado_pago_service.get_authorized_payment",
            return_value=invoice_data,
        ), patch(
            "Blueprints.services.subscription.mercado_pago_service.get_subscription",
            return_value=subscription_data,
        ), patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
            return_value=payment_data,
        ):
            response = self.post_mercado_pago_payload(
                {
                    "id": 1005,
                    "type": "subscription_authorized_payment",
                    "data": {"id": "invoice_rejected"},
                },
                "invoice_rejected",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user_plan_state(user_id), ("pro", "active"))
        self.assertEqual(
            self.subscription_payment_state("sub_recurring_rejected")[0],
            "rejected",
        )

    def test_rejected_renewal_removes_pro_after_paid_period_expired(self) -> None:
        paid_through_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        user_id = self.create_user("recorrente-expirado@example.com", "pro", "active")
        self.create_existing_paid_subscription(
            user_id,
            "sub_recurring_expired",
            "pay_expired_period",
            paid_through_at,
        )
        subscription_data = self.provider_subscription_data(
            user_id,
            "sub_recurring_expired",
            "authorized",
        )
        payment_data = self.provider_payment_data(
            user_id,
            "pay_expired_rejected",
            "rejected",
            "visa",
            "credit_card",
        )
        payment_data["preapproval_id"] = "sub_recurring_expired"
        invoice_data = {
            "id": "invoice_expired_rejected",
            "preapproval_id": "sub_recurring_expired",
            "status": "recycling",
            "payment": {"id": "pay_expired_rejected", "status": "rejected"},
        }

        with patch(
            "Blueprints.services.subscription.mercado_pago_service.get_authorized_payment",
            return_value=invoice_data,
        ), patch(
            "Blueprints.services.subscription.mercado_pago_service.get_subscription",
            return_value=subscription_data,
        ), patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
            return_value=payment_data,
        ):
            response = self.post_mercado_pago_payload(
                {
                    "id": 1006,
                    "type": "subscription_authorized_payment",
                    "data": {"id": "invoice_expired_rejected"},
                },
                "invoice_expired_rejected",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user_plan_state(user_id), ("free", "inactive"))

    def test_approved_pix_payment_sets_user_plan_to_pro_for_30_days(self) -> None:
        user_id = self.create_user("pix@example.com", "free", "inactive")
        provider_data = self.provider_payment_data(user_id, "pay_pix", "approved", "pix", "bank_transfer")

        with patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
            return_value=provider_data,
        ):
            response = self.post_mercado_pago_payload(
                {"id": 2001, "type": "payment", "data": {"id": "pay_pix"}},
                "pay_pix",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user_plan_state(user_id), ("pro", "active"))
        self.assertEqual(self.payment_state("pay_pix")[0], "pix")
        self.assertIsNotNone(self.payment_state("pay_pix")[2])
        self.assertIsNotNone(self.payment_approved_at("pay_pix"))

    def test_requested_api_webhook_alias_processes_approved_pix(self) -> None:
        user_id = self.create_user("pix-alias@example.com", "free", "inactive")
        provider_data = self.provider_payment_data(user_id, "pay_pix_alias", "approved", "pix", "bank_transfer")
        with patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
            return_value=provider_data,
        ):
            response = self.post_mercado_pago_payload(
                {"id": 2010, "type": "payment", "data": {"id": "pay_pix_alias"}},
                "pay_pix_alias",
                path="/api/webhooks/mercadopago",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user_plan_state(user_id), ("pro", "active"))

    def test_approved_debit_payment_sets_user_plan_to_pro_for_30_days(self) -> None:
        user_id = self.create_user("debito@example.com", "free", "inactive")
        provider_data = self.provider_payment_data(user_id, "pay_debit", "approved", "debvisa", "debit_card")

        with patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
            return_value=provider_data,
        ):
            response = self.post_mercado_pago_payload(
                {"id": 2002, "type": "payment", "data": {"id": "pay_debit"}},
                "pay_debit",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user_plan_state(user_id), ("pro", "active"))
        self.assertEqual(self.payment_state("pay_debit")[0], "debit_card")
        self.assertIsNotNone(self.payment_state("pay_debit")[2])

    def test_approved_checkout_credit_payment_sets_user_plan_to_pro_for_30_days(self) -> None:
        user_id = self.create_user("credito-avulso@example.com", "free", "inactive")
        provider_data = self.provider_payment_data(user_id, "pay_credit", "approved", "visa", "credit_card")

        with patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
            return_value=provider_data,
        ):
            response = self.post_mercado_pago_payload(
                {"id": 2004, "type": "payment", "data": {"id": "pay_credit"}},
                "pay_credit",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user_plan_state(user_id), ("pro", "active"))
        self.assertEqual(self.payment_state("pay_credit")[0], "credit_card")
        self.assertIsNotNone(self.payment_state("pay_credit")[2])

    def test_rejected_payment_does_not_set_user_plan_to_pro(self) -> None:
        user_id = self.create_user("recusado@example.com", "free", "inactive")
        provider_data = self.provider_payment_data(user_id, "pay_rejected", "rejected", "pix", "bank_transfer")

        with patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
            return_value=provider_data,
        ):
            response = self.post_mercado_pago_payload(
                {"id": 2003, "type": "payment", "data": {"id": "pay_rejected"}},
                "pay_rejected",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user_plan_state(user_id), ("free", "inactive"))
        self.assertIsNone(self.payment_state("pay_rejected")[2])

    def test_cancelled_payment_is_persisted_without_pro_access(self) -> None:
        user_id = self.create_user("cancelado@example.com", "free", "inactive")
        provider_data = self.provider_payment_data(
            user_id,
            "pay_cancelled",
            "cancelled",
            "pix",
            "bank_transfer",
        )

        with patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
            return_value=provider_data,
        ):
            response = self.post_mercado_pago_payload(
                {"id": 2005, "type": "payment", "data": {"id": "pay_cancelled"}},
                "pay_cancelled",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user_plan_state(user_id), ("free", "inactive"))
        self.assertEqual(self.payment_state("pay_cancelled")[1], "cancelled")

    def test_refunded_payment_revokes_its_unexpired_access(self) -> None:
        user_id = self.create_user("estornado@example.com", "pro", "active")
        with self.app.app_context():
            db.session.add(
                Payment(
                    user_id=user_id,
                    provider_payment_id="pay_refunded",
                    external_reference=f"boost:user:{user_id}",
                    plan="BOOSTCONVERT_PRO",
                    payment_method="pix",
                    status="approved",
                    amount="19.90",
                    currency="BRL",
                    approved_at=datetime.now(timezone.utc),
                    premium_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                )
            )
            db.session.commit()
        provider_data = self.provider_payment_data(
            user_id,
            "pay_refunded",
            "refunded",
            "pix",
            "bank_transfer",
        )

        with patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
            return_value=provider_data,
        ):
            response = self.post_mercado_pago_payload(
                {"id": 2008, "type": "payment", "data": {"id": "pay_refunded"}},
                "pay_refunded",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.payment_state("pay_refunded")[1], "refunded")
        self.assertEqual(self.user_plan_state(user_id), ("free", "inactive"))

    def test_approved_payment_with_wrong_amount_is_rejected(self) -> None:
        user_id = self.create_user("valor-invalido@example.com", "free", "inactive")
        provider_data = self.provider_payment_data(
            user_id,
            "pay_wrong_amount",
            "approved",
            "pix",
            "bank_transfer",
        )
        provider_data["transaction_amount"] = "0.01"

        with patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
            return_value=provider_data,
        ):
            response = self.post_mercado_pago_payload(
                {"id": 2006, "type": "payment", "data": {"id": "pay_wrong_amount"}},
                "pay_wrong_amount",
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.user_plan_state(user_id), ("free", "inactive"))
        with self.app.app_context():
            self.assertIsNone(Payment.query.filter_by(provider_payment_id="pay_wrong_amount").first())

    def test_invalid_signature_is_rejected(self) -> None:
        response = self.client.post(
            "/webhooks/mercado-pago?data.id=sub_123",
            json={"id": 1004, "type": "subscription_preapproval", "data": {"id": "sub_123"}},
            headers={"x-request-id": "req-1", "x-signature": "ts=1,v1=wrong"},
        )

        self.assertEqual(response.status_code, 401)

    def test_webhook_manifest_normalizes_alphanumeric_resource_id(self) -> None:
        self.assertEqual(
            build_webhook_manifest("PAY-AbC123", "request-id", "123"),
            "id:pay-abc123;request-id:request-id;ts:123;",
        )

    def test_signed_query_id_must_match_payload_resource_id(self) -> None:
        user_id = self.create_user("payload-divergente@example.com", "free", "inactive")
        provider_data = self.provider_payment_data(
            user_id,
            "pay_payload",
            "approved",
            "pix",
            "bank_transfer",
        )
        with patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
            return_value=provider_data,
        ) as get_payment:
            response = self.post_mercado_pago_payload(
                {"id": 2007, "type": "payment", "data": {"id": "pay_payload"}},
                "different_query_id",
            )

        self.assertEqual(response.status_code, 401)
        get_payment.assert_not_called()
        self.assertEqual(self.user_plan_state(user_id), ("free", "inactive"))

    def test_invalid_json_returns_bad_request(self) -> None:
        response = self.client.post(
            "/webhooks/mercado-pago?data.id=sub_123",
            content_type="application/json",
            data="{invalid-json",
        )

        self.assertEqual(response.status_code, 400)

    def create_user(self, email: str, plano: str, status_assinatura: str) -> int:
        with self.app.app_context():
            user = Usuario(
                email=email,
                senha=None,
                plano=plano,
                status_assinatura=status_assinatura,
            )
            db.session.add(user)
            db.session.commit()
            return user.id

    def user_plan_state(self, user_id: int) -> tuple[str, str]:
        with self.app.app_context():
            user = db.session.get(Usuario, user_id)
            return user.plano, user.status_assinatura

    def create_existing_paid_subscription(
        self,
        user_id: int,
        provider_subscription_id: str,
        provider_payment_id: str,
        paid_through_at: datetime,
    ) -> None:
        with self.app.app_context():
            db.session.add(
                Subscription(
                    user_id=user_id,
                    provider_subscription_id=provider_subscription_id,
                    provider_payment_id=provider_payment_id,
                    status="authorized",
                    latest_payment_status="approved",
                    paid_through_at=paid_through_at,
                    next_payment_at=paid_through_at,
                    amount="19.90",
                    currency="BRL",
                )
            )
            db.session.add(
                Payment(
                    user_id=user_id,
                    provider_subscription_id=provider_subscription_id,
                    provider_payment_id=provider_payment_id,
                    external_reference=f"boost:user:{user_id}",
                    plan="BOOSTCONVERT_PRO",
                    payment_method="credit_card",
                    status="approved",
                    amount="19.90",
                    currency="BRL",
                    approved_at=paid_through_at - timedelta(days=30),
                    premium_expires_at=paid_through_at,
                )
            )
            db.session.commit()

    def subscription_status(self, provider_subscription_id: str) -> str:
        with self.app.app_context():
            subscription = Subscription.query.filter_by(
                provider_subscription_id=provider_subscription_id,
            ).one()
            return subscription.status

    def subscription_payment_state(
        self,
        provider_subscription_id: str,
    ) -> tuple[str | None, object]:
        with self.app.app_context():
            subscription = Subscription.query.filter_by(
                provider_subscription_id=provider_subscription_id,
            ).one()
            return subscription.latest_payment_status, subscription.paid_through_at

    def webhook_event_count(self) -> int:
        with self.app.app_context():
            return PaymentWebhookEvent.query.count()

    def payment_state(self, provider_payment_id: str) -> tuple[str, str, object]:
        with self.app.app_context():
            payment = Payment.query.filter_by(provider_payment_id=provider_payment_id).one()
            return payment.payment_method, payment.status, payment.premium_expires_at

    def payment_approved_at(self, provider_payment_id: str):
        with self.app.app_context():
            return Payment.query.filter_by(provider_payment_id=provider_payment_id).one().approved_at

    def provider_subscription_data(
        self,
        user_id: int,
        provider_subscription_id: str,
        status: str,
    ) -> dict[str, object]:
        return {
            "id": provider_subscription_id,
            "external_reference": f"boost:user:{user_id}",
            "status": status,
            "auto_recurring": {
                "transaction_amount": "19.90",
                "currency_id": "BRL",
            },
            "next_payment_date": "2026-08-05T00:00:00Z",
        }

    def provider_payment_data(
        self,
        user_id: int,
        provider_payment_id: str,
        status: str,
        payment_method_id: str,
        payment_type_id: str,
    ) -> dict[str, object]:
        return {
            "id": provider_payment_id,
            "external_reference": f"boost:user:{user_id}",
            "status": status,
            "payment_method_id": payment_method_id,
            "payment_type_id": payment_type_id,
            "transaction_amount": "19.90",
            "currency_id": "BRL",
            "date_created": "2026-07-31T10:15:00Z",
            "date_approved": "2026-07-31T10:16:00Z" if status == "approved" else None,
            "metadata": {"user_id": user_id, "plan": "BOOSTCONVERT_PRO"},
        }

    def post_mercado_pago_payload(
        self,
        payload: dict[str, object],
        data_id: str,
        path: str = "/webhooks/mercado-pago",
    ) -> TestResponse:
        x_request_id = "request-id-123"
        ts = "1781009491"
        manifest = build_webhook_manifest(data_id, x_request_id, ts)
        signature = hmac.new(
            WEBHOOK_SECRET.encode("utf-8"),
            manifest.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return self.client.post(
            f"{path}?data.id={data_id}",
            content_type="application/json",
            data=_serialize_payload(payload),
            headers={
                "x-request-id": x_request_id,
                "x-signature": f"ts={ts},v1={signature}",
            },
        )


if __name__ == "__main__":
    unittest.main()
