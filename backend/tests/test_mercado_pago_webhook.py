import hashlib
import hmac
import json
import sys
import time
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from sqlalchemy.exc import IntegrityError


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.main.webhook_routes import webhook_bp
from Blueprints.services.subscription.mercado_pago_service import (
    MercadoPagoWebhookResult,
    build_webhook_manifest,
    process_mercado_pago_webhook,
    utc_now,
)
from extensions import db
from models import Payment, PaymentWebhookEvent, Usuario


WEBHOOK_SECRET = "test-mercado-pago-webhook-secret"


class MercadoPagoWebhookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            MERCADO_PAGO_ACCESS_TOKEN="TEST-token",
            MERCADO_PAGO_WEBHOOK_SECRET=WEBHOOK_SECRET,
            MERCADO_PAGO_WEBHOOK_TOLERANCE_SECONDS=300,
            MERCADO_PAGO_ENVIRONMENT="test",
            MERCADO_PAGO_COLLECTOR_ID="123456",
            MERCADO_PAGO_PLAN_PRICE="19.90",
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

    def test_approved_pix_grants_30_days_only_after_provider_get(self) -> None:
        user_id, payment_id = self.create_attempt("pix", "pix", "bank_transfer")
        provider_data = self.provider_data(user_id, payment_id, "approved", "pix", "bank_transfer")
        with patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
            return_value=provider_data,
        ) as get_payment:
            response = self.post_payment_event(1001, payment_id)

        self.assertEqual(response.status_code, 200)
        get_payment.assert_called_once_with(payment_id)
        with self.app.app_context():
            payment = Payment.query.filter_by(provider_payment_id=payment_id).one()
            user = db.session.get(Usuario, user_id)
            self.assertEqual((user.plano, user.status_assinatura), ("pro", "active"))
            self.assertEqual(payment.premium_expires_at - payment.approved_at, timedelta(days=30))

    def test_approved_credit_card_grants_30_days(self) -> None:
        user_id, payment_id = self.create_attempt("credit_card", "visa", "credit_card")
        provider_data = self.provider_data(
            user_id, payment_id, "approved", "visa", "credit_card"
        )
        with patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
            return_value=provider_data,
        ):
            response = self.post_payment_event(1002, payment_id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user_state(user_id), ("pro", "active"))

    def test_pending_or_rejected_payment_never_grants_access(self) -> None:
        for index, status in enumerate(("pending", "in_process", "rejected"), start=1):
            with self.subTest(status=status):
                with self.app.app_context():
                    db.drop_all()
                    db.create_all()
                user_id, payment_id = self.create_attempt("pix", "pix", "bank_transfer")
                provider_data = self.provider_data(
                    user_id, payment_id, status, "pix", "bank_transfer"
                )
                with patch(
                    "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
                    return_value=provider_data,
                ):
                    response = self.post_payment_event(1100 + index, payment_id)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.user_state(user_id), ("free", "inactive"))

    def test_webhook_before_create_response_correlates_original_attempt(self) -> None:
        user_id, payment_id = self.create_attempt("pix", "pix", "bank_transfer")
        with self.app.app_context():
            payment = Payment.query.one()
            payment.provider_payment_id = None
            db.session.commit()
            original_local_id = payment.id
        provider_data = self.provider_data(
            user_id, payment_id, "approved", "pix", "bank_transfer"
        )
        with patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
            return_value=provider_data,
        ):
            response = self.post_payment_event(1201, payment_id)

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(Payment.query.count(), 1)
            payment = Payment.query.one()
            self.assertEqual(payment.id, original_local_id)
            self.assertEqual(payment.provider_payment_id, payment_id)
            self.assertIsNotNone(payment.premium_expires_at)

    def test_concurrent_duplicate_event_integrity_error_reloads_winner(self) -> None:
        payload = {"id": 1301, "type": "payment", "data": {"id": "pay_race"}}
        dispatched = MercadoPagoWebhookResult("processed", "payment", "pay_race")
        with self.app.test_request_context("/api/webhooks/mercadopago", method="POST"), patch(
            "Blueprints.services.subscription.mercado_pago_service.is_duplicate_webhook_event",
            side_effect=[False, True],
        ), patch(
            "Blueprints.services.subscription.mercado_pago_service.dispatch_mercado_pago_webhook",
            return_value=dispatched,
        ), patch(
            "Blueprints.services.subscription.mercado_pago_service.record_webhook_event"
        ), patch(
            "Blueprints.services.subscription.mercado_pago_service.db.session.commit",
            side_effect=IntegrityError("INSERT", {}, Exception("unique")),
        ), patch(
            "Blueprints.services.subscription.mercado_pago_service.db.session.rollback"
        ) as rollback:
            result = process_mercado_pago_webhook(payload)
        self.assertTrue(result.duplicate)
        rollback.assert_called_once()

    def test_provider_contract_mismatches_never_grant_access(self) -> None:
        mutations = {
            "reference": lambda data: data.update(external_reference="boost:payment:aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee:user:999"),
            "amount": lambda data: data.update(transaction_amount="0.01"),
            "currency": lambda data: data.update(currency_id="USD"),
            "plan": lambda data: data["metadata"].update(plan="OTHER"),
            "method": lambda data: data.update(payment_method_id="pix", payment_type_id="bank_transfer"),
            "collector": lambda data: data.update(collector_id=999999),
            "live_mode": lambda data: data.update(live_mode=True),
            "attempt_metadata": lambda data: data["metadata"].update(attempt_id="ffffffff-ffff-4fff-8fff-ffffffffffff"),
            "user_metadata": lambda data: data["metadata"].update(user_id=999999),
        }
        for index, (name, mutate) in enumerate(mutations.items(), start=1):
            with self.subTest(name=name):
                with self.app.app_context():
                    db.drop_all()
                    db.create_all()
                user_id, payment_id = self.create_attempt(
                    "credit_card", "visa", "credit_card"
                )
                provider_data = self.provider_data(
                    user_id, payment_id, "approved", "visa", "credit_card"
                )
                mutate(provider_data)
                with patch(
                    "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
                    return_value=provider_data,
                ):
                    response = self.post_payment_event(2000 + index, payment_id)
                self.assertEqual(response.status_code, 502)
                self.assertEqual(self.user_state(user_id), ("free", "inactive"))

    def test_duplicate_notification_id_is_idempotent_across_request_ids(self) -> None:
        user_id, payment_id = self.create_attempt("pix", "pix", "bank_transfer")
        provider_data = self.provider_data(user_id, payment_id, "approved", "pix", "bank_transfer")
        with patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
            return_value=provider_data,
        ) as get_payment:
            first = self.post_payment_event(3001, payment_id, request_id="delivery-a")
            second = self.post_payment_event(3001, payment_id, request_id="delivery-b")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json["duplicate"])
        self.assertEqual(get_payment.call_count, 1)
        with self.app.app_context():
            self.assertEqual(PaymentWebhookEvent.query.count(), 1)

    def test_refund_removes_only_refunded_access(self) -> None:
        user_id, payment_id = self.create_attempt("credit_card", "visa", "credit_card")
        approved = self.provider_data(user_id, payment_id, "approved", "visa", "credit_card")
        refunded = self.provider_data(user_id, payment_id, "refunded", "visa", "credit_card")
        with patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
            side_effect=[approved, refunded],
        ):
            self.assertEqual(self.post_payment_event(4001, payment_id).status_code, 200)
            self.assertEqual(self.post_payment_event(4002, payment_id).status_code, 200)

        self.assertEqual(self.user_state(user_id), ("free", "inactive"))
        with self.app.app_context():
            payment = Payment.query.filter_by(provider_payment_id=payment_id).one()
            self.assertEqual(payment.status, "refunded")

    def test_refund_preserves_access_from_another_valid_payment(self) -> None:
        user_id, payment_id = self.create_attempt("credit_card", "visa", "credit_card")
        with self.app.app_context():
            db.session.add(
                Payment(
                    user_id=user_id,
                    provider_payment_id="pay_other",
                    external_reference=f"boost:user:{user_id}",
                    payment_method="pix",
                    status="approved",
                    amount="19.90",
                    currency="BRL",
                    approved_at=utc_now(),
                    premium_expires_at=utc_now() + timedelta(days=20),
                )
            )
            user = db.session.get(Usuario, user_id)
            user.plano = "pro"
            user.status_assinatura = "active"
            db.session.commit()
        refunded = self.provider_data(user_id, payment_id, "refunded", "visa", "credit_card")
        with patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
            return_value=refunded,
        ):
            response = self.post_payment_event(5001, payment_id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user_state(user_id), ("pro", "active"))

    def test_stale_or_invalid_signature_is_rejected_before_provider_get(self) -> None:
        user_id, payment_id = self.create_attempt("pix", "pix", "bank_transfer")
        with patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment"
        ) as get_payment:
            stale = self.post_payment_event(6001, payment_id, timestamp=1)
            invalid = self.client.post(
                f"/api/webhooks/mercadopago?data.id={payment_id}",
                json={"id": 6002, "type": "payment", "data": {"id": payment_id}},
                headers={"x-request-id": "invalid", "x-signature": f"ts={int(time.time())},v1=wrong"},
            )
        self.assertEqual(stale.status_code, 401)
        self.assertEqual(invalid.status_code, 401)
        get_payment.assert_not_called()

    def test_legacy_webhook_is_disabled(self) -> None:
        response = self.client.post("/webhook", json={"type": "payment", "data": {"id": "1"}})
        self.assertEqual(response.status_code, 410)

    def test_persisted_webhook_payload_is_sanitized(self) -> None:
        user_id, payment_id = self.create_attempt("pix", "pix", "bank_transfer")
        provider_data = self.provider_data(user_id, payment_id, "pending", "pix", "bank_transfer")
        with patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
            return_value=provider_data,
        ):
            response = self.post_payment_event(7001, payment_id, extra={"token": "must-not-persist"})
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            stored = PaymentWebhookEvent.query.one().payload
            self.assertNotIn("token", stored)
            self.assertNotIn("must-not-persist", repr(stored))

    def create_attempt(
        self,
        payment_method: str,
        provider_method: str,
        payment_type: str,
    ) -> tuple[int, str]:
        with self.app.app_context():
            user = Usuario(email=f"{payment_method}@example.com", plano="free", status_assinatura="inactive")
            db.session.add(user)
            db.session.flush()
            attempt_id = "11111111-2222-4333-8444-555555555555"
            payment_id = f"pay_{payment_method}"
            db.session.add(
                Payment(
                    user_id=user.id,
                    attempt_id=attempt_id,
                    provider_payment_id=payment_id,
                    external_reference=f"boost:payment:{attempt_id}:user:{user.id}",
                    plan="BOOSTCONVERT_PRO",
                    idempotency_key="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
                    payment_method=payment_method,
                    provider_payment_method_id=provider_method,
                    payment_type=payment_type,
                    status="pending",
                    amount="19.90",
                    currency="BRL",
                )
            )
            db.session.commit()
            return user.id, payment_id

    def provider_data(
        self,
        user_id: int,
        payment_id: str,
        status: str,
        payment_method_id: str,
        payment_type_id: str,
    ) -> dict:
        attempt_id = "11111111-2222-4333-8444-555555555555"
        return {
            "id": payment_id,
            "external_reference": f"boost:payment:{attempt_id}:user:{user_id}",
            "status": status,
            "payment_method_id": payment_method_id,
            "payment_type_id": payment_type_id,
            "transaction_amount": "19.90",
            "currency_id": "BRL",
            "collector_id": 123456,
            "live_mode": False,
            "date_created": "2026-07-31T10:15:00Z",
            "date_approved": "2026-07-31T10:16:00Z" if status == "approved" else None,
            "metadata": {
                "user_id": user_id,
                "plan": "BOOSTCONVERT_PRO",
                "attempt_id": attempt_id,
                "payment_method": payment_type_id,
            },
        }

    def post_payment_event(
        self,
        event_id: int,
        payment_id: str,
        *,
        request_id: str = "request-id-123",
        timestamp: int | None = None,
        extra: dict | None = None,
    ):
        timestamp = int(time.time()) if timestamp is None else timestamp
        payload = {"id": event_id, "type": "payment", "data": {"id": payment_id}}
        payload.update(extra or {})
        manifest = build_webhook_manifest(payment_id, request_id, str(timestamp))
        signature = hmac.new(
            WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256
        ).hexdigest()
        return self.client.post(
            f"/api/webhooks/mercadopago?data.id={payment_id}",
            content_type="application/json",
            data=json.dumps(payload, separators=(",", ":")),
            headers={
                "x-request-id": request_id,
                "x-signature": f"ts={timestamp},v1={signature}",
            },
        )

    def user_state(self, user_id: int) -> tuple[str, str]:
        with self.app.app_context():
            user = db.session.get(Usuario, user_id)
            return user.plano, user.status_assinatura


if __name__ == "__main__":
    unittest.main()
