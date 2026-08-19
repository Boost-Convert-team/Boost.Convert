import hashlib
import hmac
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from flask import Flask

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.main.webhook_routes import webhook_bp
from Blueprints.services.payments.mercado_pago_client import MercadoPagoError
from Blueprints.services.payments.webhook_service import (
    WebhookValidationError,
    process_payment_notification,
)
from extensions import db
from models import Payment, PaymentWebhookEvent, Usuario
from security import init_security


class PaymentWebhookTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="test-secret-key-with-at-least-32-characters",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            MERCADOPAGO_ACCESS_TOKEN="test-token",
            MERCADOPAGO_WEBHOOK_SECRET="test-webhook-secret",
            MERCADOPAGO_API_BASE_URL="https://api.mercadopago.com",
            MERCADOPAGO_REQUEST_TIMEOUT_SECONDS=10,
            PRO_PLAN_PRICE="25.90",
            CSRF_ENABLED=True,
            RATE_LIMIT_ENABLED=False,
            FORCE_HTTPS=False,
        )
        db.init_app(self.app)
        init_security(self.app)
        self.app.register_blueprint(webhook_bp)
        with self.app.app_context():
            db.create_all()
            user = Usuario(email="webhook@example.com")
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_approved_payment_activates_pro_for_30_days(self):
        with self.app.app_context():
            payment = self.create_payment()
            approved_at = datetime.now(timezone.utc)
            remote = self.provider_payment(payment, "approved", approved_at=approved_at)
            result = process_payment_notification(
                self.event("evt-approved", payment.provider_payment_id),
                payment.provider_payment_id,
                client=self.gateway(remote),
            )
            stored = Payment.query.one()
            self.assertEqual(result.status, "processed")
            self.assertEqual(stored.status, "approved")
            self.assertAlmostEqual(
                (
                    stored.premium_expires_at.replace(tzinfo=timezone.utc) - approved_at
                ).total_seconds(),
                30 * 86400,
                delta=2,
            )
            self.assertEqual(db.session.get(Usuario, self.user_id).plano, "pro")

    def test_pending_and_in_process_do_not_activate_pro(self):
        with self.app.app_context():
            for index, status in enumerate(("pending", "in_process")):
                payment = self.create_payment(payment_id=str(2000 + index))
                process_payment_notification(
                    self.event(f"evt-{status}", payment.provider_payment_id),
                    payment.provider_payment_id,
                    client=self.gateway(self.provider_payment(payment, status)),
                )
            self.assertEqual(db.session.get(Usuario, self.user_id).plano, "free")

    def test_rejected_payment_does_not_activate_pro(self):
        with self.app.app_context():
            payment = self.create_payment()
            process_payment_notification(
                self.event("evt-rejected", payment.provider_payment_id),
                payment.provider_payment_id,
                client=self.gateway(self.provider_payment(payment, "rejected")),
            )
            self.assertEqual(Payment.query.one().status, "rejected")
            self.assertEqual(db.session.get(Usuario, self.user_id).plano, "free")

    def test_duplicate_event_is_idempotent(self):
        with self.app.app_context():
            payment = self.create_payment()
            gateway = self.gateway(self.provider_payment(payment, "approved"))
            event = self.event("evt-duplicate", payment.provider_payment_id)
            process_payment_notification(
                event, payment.provider_payment_id, client=gateway
            )
            expiration = Payment.query.one().premium_expires_at
            duplicate = process_payment_notification(
                event, payment.provider_payment_id, client=gateway
            )
            self.assertTrue(duplicate.duplicate)
            self.assertEqual(Payment.query.one().premium_expires_at, expiration)
            self.assertEqual(PaymentWebhookEvent.query.count(), 1)
            gateway.get_payment.assert_called_once()

    def test_distinct_update_event_does_not_add_another_30_days(self):
        with self.app.app_context():
            payment = self.create_payment()
            remote = self.provider_payment(payment, "approved")
            gateway = self.gateway(remote)
            process_payment_notification(
                self.event("evt-created", payment.provider_payment_id),
                payment.provider_payment_id,
                client=gateway,
            )
            expiration = Payment.query.one().premium_expires_at
            process_payment_notification(
                self.event("evt-updated", payment.provider_payment_id),
                payment.provider_payment_id,
                client=gateway,
            )
            self.assertEqual(Payment.query.one().premium_expires_at, expiration)
            self.assertEqual(PaymentWebhookEvent.query.count(), 2)

    def test_tampered_amount_is_rejected(self):
        with self.app.app_context():
            payment = self.create_payment()
            remote = self.provider_payment(payment, "approved")
            remote["transaction_amount"] = "1.00"
            with self.assertRaises(WebhookValidationError):
                process_payment_notification(
                    self.event("evt-tampered", payment.provider_payment_id),
                    payment.provider_payment_id,
                    client=self.gateway(remote),
                )
            self.assertEqual(db.session.get(Usuario, self.user_id).plano, "free")

    def test_wrong_external_reference_is_rejected(self):
        with self.app.app_context():
            payment = self.create_payment()
            remote = self.provider_payment(payment, "approved")
            remote["external_reference"] = "boost:payment:other"
            with self.assertRaises(WebhookValidationError):
                process_payment_notification(
                    self.event("evt-reference", payment.provider_payment_id),
                    payment.provider_payment_id,
                    client=self.gateway(remote),
                )

    @patch("Blueprints.services.payments.webhook_service.MercadoPagoClient.get_payment")
    def test_route_validates_signature_and_fetches_official_payment(self, get_payment):
        with self.app.app_context():
            payment = self.create_payment()
            payment_id = payment.provider_payment_id
            get_payment.return_value = self.provider_payment(payment, "approved")
        response = self.signed_webhook(
            self.event("evt-route", payment_id), payment_id, "request-108"
        )
        self.assertEqual(response.status_code, 200)
        get_payment.assert_called_once_with(payment_id)
        with self.app.app_context():
            self.assertEqual(db.session.get(Usuario, self.user_id).plano, "pro")

    def test_invalid_signature_changes_nothing(self):
        response = self.client.post(
            "/webhooks/mercado-pago?data.id=1001",
            json=self.event("evt-invalid", "1001"),
            headers={
                "X-Request-Id": "request-109",
                "X-Signature": "ts=1742505638683,v1=invalid",
            },
        )
        self.assertEqual(response.status_code, 401)
        with self.app.app_context():
            self.assertEqual(PaymentWebhookEvent.query.count(), 0)

    def test_subscription_event_is_ignored_without_provider_call(self):
        with self.app.app_context():
            gateway = Mock()
            result = process_payment_notification(
                self.event("evt-subscription", "sub-101", "subscription_preapproval"),
                "sub-101",
                client=gateway,
            )
            self.assertEqual(result.status, "ignored")
            gateway.get_payment.assert_not_called()

    def test_missing_local_payment_is_rejected(self):
        with self.app.app_context():
            remote = {
                "id": 9999,
                "external_reference": "boost:payment:unknown",
            }
            with self.assertRaises(WebhookValidationError):
                process_payment_notification(
                    self.event("evt-unknown", "9999"),
                    "9999",
                    client=self.gateway(remote),
                )

    @patch(
        "Blueprints.services.payments.webhook_service.MercadoPagoClient.get_payment",
        side_effect=MercadoPagoError(
            operation="payment_get",
            endpoint="/v1/payments/9999",
            status=404,
            provider_code="not_found",
            provider_message="resource not found",
        ),
    )
    def test_missing_provider_resource_returns_controlled_retry(self, _get_payment):
        response = self.signed_webhook(
            self.event("evt-missing", "9999"), "9999", "request-missing"
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["error"], "provider_unavailable")

    def test_refund_revokes_only_refunded_payment_access(self):
        with self.app.app_context():
            payment = self.create_payment(status="approved")
            payment.premium_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
            payment.user.plano = "pro"
            payment.user.status_assinatura = "active"
            db.session.commit()
            process_payment_notification(
                self.event("evt-refund", payment.provider_payment_id),
                payment.provider_payment_id,
                client=self.gateway(self.provider_payment(payment, "refunded")),
            )
            self.assertEqual(Payment.query.one().status, "refunded")
            self.assertEqual(db.session.get(Usuario, self.user_id).plano, "free")

    def signed_webhook(self, payload, resource_id, request_id):
        timestamp = "1742505638683"
        manifest = f"id:{resource_id.lower()};request-id:{request_id};ts:{timestamp};"
        digest = hmac.new(
            b"test-webhook-secret", manifest.encode(), hashlib.sha256
        ).hexdigest()
        return self.client.post(
            f"/webhooks/mercado-pago?data.id={resource_id}",
            json=payload,
            headers={
                "X-Request-Id": request_id,
                "X-Signature": f"ts={timestamp},v1={digest}",
            },
        )

    def create_payment(self, payment_id="1001", status="pending"):
        attempt_id = str(uuid4())
        payment = Payment(
            user_id=self.user_id,
            provider="mercado_pago",
            provider_payment_id=payment_id,
            external_reference=f"boost:payment:{self.user_id}:{attempt_id}",
            plan="PRO",
            attempt_id=attempt_id,
            idempotency_key=attempt_id,
            payment_method="credit_card",
            status=status,
            amount="25.90",
            currency="BRL",
        )
        db.session.add(payment)
        db.session.commit()
        return payment

    def provider_payment(self, payment, status, approved_at=None):
        approved_at = approved_at or datetime.now(timezone.utc)
        return {
            "id": int(payment.provider_payment_id),
            "status": status,
            "status_detail": "accredited" if status == "approved" else status,
            "transaction_amount": "25.90",
            "currency_id": "BRL",
            "payment_method_id": "visa",
            "payment_type_id": "credit_card",
            "external_reference": payment.external_reference,
            "metadata": {
                "user_id": payment.user_id,
                "plan": "PRO",
                "attempt_id": payment.attempt_id,
            },
            "date_created": approved_at.isoformat(),
            "date_approved": approved_at.isoformat(),
        }

    @staticmethod
    def event(event_id, resource_id, event_type="payment"):
        return {
            "id": event_id,
            "type": event_type,
            "action": f"{event_type}.updated",
            "data": {"id": resource_id},
        }

    @staticmethod
    def gateway(provider_payment):
        gateway = Mock()
        gateway.get_payment.return_value = provider_payment
        return gateway


if __name__ == "__main__":
    unittest.main()
