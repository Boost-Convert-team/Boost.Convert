import hashlib
import hmac
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from flask import Flask

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.main.webhook_routes import webhook_bp
from Blueprints.services.payments.webhook_service import process_notification
from extensions import db
from models import Payment, PaymentWebhookEvent, Subscription, Usuario
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

    def test_invalid_signature_is_rejected_before_processing(self):
        payload = self.event("evt-invalid", "sub-101", "subscription_preapproval")
        with patch("Blueprints.main.webhook_routes.process_notification") as processor:
            response = self.client.post(
                "/webhooks/mercado-pago?data.id=sub-101",
                json=payload,
                headers={
                    "X-Request-Id": "request-1",
                    "X-Signature": "ts=1,v1=invalid",
                },
            )
        self.assertEqual(response.status_code, 401)
        processor.assert_not_called()

    def test_valid_webhook_queries_provider_before_sync(self):
        with self.app.app_context():
            subscription = self.create_subscription()
            provider_subscription = self.provider_subscription(subscription)
        gateway = Mock()
        gateway.get_subscription.return_value = provider_subscription
        payload = self.event("evt-subscription", "sub-101", "subscription_preapproval")
        with patch(
            "Blueprints.services.payments.webhook_service.MercadoPagoGateway",
            return_value=gateway,
        ):
            response = self.signed_webhook(payload, "sub-101", "request-2")
        self.assertEqual(response.status_code, 200)
        gateway.get_subscription.assert_called_once_with("sub-101")
        with self.app.app_context():
            self.assertEqual(PaymentWebhookEvent.query.count(), 1)
            self.assertEqual(db.session.get(Usuario, self.user_id).plano, "free")

    def test_approved_invoice_queries_invoice_and_subscription_then_grants_pro(self):
        with self.app.app_context():
            subscription = self.create_subscription()
            gateway = Mock()
            gateway.get_invoice.return_value = self.provider_invoice(
                subscription, "approved"
            )
            gateway.get_subscription.return_value = self.provider_subscription(
                subscription
            )
            result = process_notification(
                self.event("evt-invoice", "501", "subscription_authorized_payment"),
                "501",
                gateway=gateway,
            )
            self.assertEqual(result.status, "processed")
            gateway.get_invoice.assert_called_once_with("501")
            gateway.get_subscription.assert_called_once_with("sub-101")
            stored = Subscription.query.one()
            self.assertEqual(stored.latest_payment_status, "approved")
            self.assertIsNotNone(stored.paid_through_at)
            self.assertEqual(
                Payment.query.one().payment_method, "recurring_subscription"
            )
            self.assertEqual(db.session.get(Usuario, self.user_id).plano, "pro")

    def test_pending_invoice_does_not_grant_pro(self):
        with self.app.app_context():
            subscription = self.create_subscription()
            gateway = Mock()
            gateway.get_invoice.return_value = self.provider_invoice(
                subscription, "pending"
            )
            gateway.get_subscription.return_value = self.provider_subscription(
                subscription
            )
            process_notification(
                self.event("evt-pending", "501", "subscription_authorized_payment"),
                "501",
                gateway=gateway,
            )
            self.assertEqual(db.session.get(Usuario, self.user_id).plano, "free")

    def test_duplicate_notification_is_idempotent(self):
        with self.app.app_context():
            subscription = self.create_subscription()
            gateway = Mock()
            gateway.get_subscription.return_value = self.provider_subscription(
                subscription
            )
            payload = self.event("evt-duplicate", "sub-101", "subscription_preapproval")
            process_notification(payload, "sub-101", gateway=gateway)
            duplicate = process_notification(payload, "sub-101", gateway=gateway)
            self.assertTrue(duplicate.duplicate)
            gateway.get_subscription.assert_called_once()
            self.assertEqual(PaymentWebhookEvent.query.count(), 1)

    def signed_webhook(self, payload, resource_id, request_id):
        timestamp = str(int(time.time()))
        manifest = f"id:{resource_id};request-id:{request_id};ts:{timestamp};"
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

    def create_subscription(self):
        key = str(uuid4())
        subscription = Subscription(
            user_id=self.user_id,
            provider="mercado_pago",
            provider_subscription_id="sub-101",
            external_reference=f"boost:subscription:{self.user_id}:{key}",
            checkout_idempotency_key=key,
            plan="PRO",
            status="active",
            amount="25.90",
            currency="BRL",
        )
        db.session.add(subscription)
        db.session.commit()
        return subscription

    @staticmethod
    def provider_subscription(subscription):
        now = datetime.now(timezone.utc)
        return {
            "id": subscription.provider_subscription_id,
            "external_reference": subscription.external_reference,
            "status": "authorized",
            "auto_recurring": {
                "frequency": 1,
                "frequency_type": "months",
                "transaction_amount": "25.90",
                "currency_id": "BRL",
            },
            "date_created": now.isoformat(),
            "next_payment_date": (now + timedelta(days=30)).isoformat(),
        }

    @staticmethod
    def provider_invoice(subscription, status):
        now = datetime.now(timezone.utc)
        return {
            "id": 501,
            "preapproval_id": subscription.provider_subscription_id,
            "external_reference": subscription.external_reference,
            "transaction_amount": "25.90",
            "currency_id": "BRL",
            "date_created": now.isoformat(),
            "debit_date": now.isoformat(),
            "payment": {
                "id": 2001,
                "status": status,
                "status_detail": "accredited" if status == "approved" else status,
            },
        }

    @staticmethod
    def event(event_id, resource_id, event_type):
        return {
            "id": event_id,
            "type": event_type,
            "action": f"{event_type}.updated",
            "data": {"id": resource_id},
        }


if __name__ == "__main__":
    unittest.main()
