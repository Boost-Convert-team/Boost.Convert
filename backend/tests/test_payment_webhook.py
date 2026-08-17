import hashlib
import hmac
import sys
import unittest
from datetime import datetime, timezone
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
    process_subscription_notification,
)
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

    def test_authorized_subscription_without_paid_invoice_does_not_activate_pro(self):
        with self.app.app_context():
            subscription = self.create_subscription()
            gateway = self.gateway(
                self.provider_subscription(subscription, "authorized")
            )
            process_subscription_notification(
                self.event("evt-sub", "subscription_preapproval", "sub-101"),
                "sub-101",
                client=gateway,
            )
            self.assertEqual(Subscription.query.one().status, "active")
            self.assertEqual(db.session.get(Usuario, self.user_id).plano, "free")

    def test_approved_recurring_invoice_activates_pro_until_next_charge(self):
        with self.app.app_context():
            subscription = self.create_subscription()
            gateway = self.gateway(
                self.provider_subscription(subscription, "authorized"),
                self.provider_invoice(subscription, "approved", "501", "9001"),
            )
            result = process_subscription_notification(
                self.event("evt-invoice", "subscription_authorized_payment", "501"),
                "501",
                client=gateway,
            )
            self.assertEqual(result.status, "processed")
            self.assertEqual(db.session.get(Usuario, self.user_id).plano, "pro")
            stored = Subscription.query.one()
            self.assertEqual(stored.latest_payment_status, "approved")
            self.assertEqual(
                stored.paid_through_at.replace(tzinfo=timezone.utc).isoformat(),
                "2026-09-17T12:00:00+00:00",
            )
            self.assertEqual(Payment.query.one().provider_invoice_id, "501")

    def test_rejected_renewal_does_not_extend_entitlement(self):
        with self.app.app_context():
            subscription = self.create_subscription()
            subscription.paid_through_at = datetime.fromisoformat(
                "2026-08-20T12:00:00+00:00"
            )
            db.session.commit()
            gateway = self.gateway(
                self.provider_subscription(subscription, "authorized"),
                self.provider_invoice(subscription, "rejected", "502", "9002"),
            )
            process_subscription_notification(
                self.event("evt-rejected", "subscription_authorized_payment", "502"),
                "502",
                client=gateway,
            )
            self.assertEqual(Subscription.query.one().latest_payment_status, "rejected")
            self.assertEqual(
                Subscription.query.one()
                .paid_through_at.replace(tzinfo=timezone.utc)
                .isoformat(),
                "2026-08-20T12:00:00+00:00",
            )

    def test_duplicate_event_is_idempotent(self):
        with self.app.app_context():
            subscription = self.create_subscription()
            gateway = self.gateway(
                self.provider_subscription(subscription, "authorized"),
                self.provider_invoice(subscription, "approved", "503", "9003"),
            )
            event = self.event(
                "evt-duplicate", "subscription_authorized_payment", "503"
            )
            process_subscription_notification(event, "503", client=gateway)
            duplicate = process_subscription_notification(event, "503", client=gateway)
            self.assertTrue(duplicate.duplicate)
            self.assertEqual(Payment.query.count(), 1)
            self.assertEqual(PaymentWebhookEvent.query.count(), 1)
            gateway.get_authorized_payment.assert_called_once()

    def test_tampered_amount_is_rejected(self):
        with self.app.app_context():
            subscription = self.create_subscription()
            invoice = self.provider_invoice(subscription, "approved", "504", "9004")
            invoice["transaction_amount"] = "1.00"
            gateway = self.gateway(
                self.provider_subscription(subscription, "authorized"), invoice
            )
            with self.assertRaises(WebhookValidationError):
                process_subscription_notification(
                    self.event(
                        "evt-tampered", "subscription_authorized_payment", "504"
                    ),
                    "504",
                    client=gateway,
                )
            self.assertEqual(db.session.get(Usuario, self.user_id).plano, "free")

    @patch(
        "Blueprints.services.payments.webhook_service.MercadoPagoClient.get_subscription"
    )
    def test_route_validates_signature_and_fetches_official_subscription(
        self, get_subscription
    ):
        with self.app.app_context():
            subscription = self.create_subscription()
            get_subscription.return_value = self.provider_subscription(
                subscription, "authorized"
            )
        payload = self.event("evt-route", "subscription_preapproval", "sub-101")
        request_id = "request-108"
        timestamp = "1742505638683"
        manifest = f"id:sub-101;request-id:{request_id};ts:{timestamp};"
        digest = hmac.new(
            b"test-webhook-secret", manifest.encode(), hashlib.sha256
        ).hexdigest()
        response = self.client.post(
            "/webhooks/mercado-pago?data.id=sub-101",
            json=payload,
            headers={
                "X-Request-Id": request_id,
                "X-Signature": f"ts={timestamp},v1={digest}",
            },
        )
        self.assertEqual(response.status_code, 200)
        get_subscription.assert_called_once_with("sub-101")

    def test_invalid_signature_changes_nothing(self):
        response = self.client.post(
            "/webhooks/mercado-pago?data.id=sub-101",
            json=self.event("evt-invalid", "subscription_preapproval", "sub-101"),
            headers={
                "X-Request-Id": "request-109",
                "X-Signature": "ts=1742505638683,v1=invalid",
            },
        )
        self.assertEqual(response.status_code, 401)
        with self.app.app_context():
            self.assertEqual(PaymentWebhookEvent.query.count(), 0)

    def test_subscription_statuses_are_synchronized(self):
        expected = {
            "pending": "pending",
            "authorized": "active",
            "paused": "paused",
            "canceled": "canceled",
        }
        with self.app.app_context():
            subscription = self.create_subscription()
            for index, (provider_status, local_status) in enumerate(expected.items()):
                gateway = self.gateway(
                    self.provider_subscription(subscription, provider_status)
                )
                process_subscription_notification(
                    self.event(
                        f"evt-status-{index}",
                        "subscription_preapproval",
                        "sub-101",
                    ),
                    "sub-101",
                    client=gateway,
                )
                self.assertEqual(Subscription.query.one().status, local_status)

    def test_irrelevant_event_is_ignored_without_provider_call(self):
        with self.app.app_context():
            gateway = Mock()
            result = process_subscription_notification(
                self.event("evt-payment", "payment", "9001"),
                "9001",
                client=gateway,
            )
            self.assertEqual(result.status, "ignored")
            gateway.get_subscription.assert_not_called()
            gateway.get_authorized_payment.assert_not_called()

    def test_missing_local_subscription_is_rejected(self):
        with self.app.app_context():
            remote = {
                "id": "sub-unknown",
                "preapproval_plan_id": None,
                "external_reference": "boost:subscription:unknown",
                "status": "authorized",
                "auto_recurring": {
                    "frequency": 1,
                    "frequency_type": "months",
                    "transaction_amount": "25.90",
                    "currency_id": "BRL",
                },
            }
            with self.assertRaises(WebhookValidationError):
                process_subscription_notification(
                    self.event(
                        "evt-unknown", "subscription_preapproval", "sub-unknown"
                    ),
                    "sub-unknown",
                    client=self.gateway(remote),
                )

    @patch(
        "Blueprints.services.payments.webhook_service.MercadoPagoClient.get_subscription",
        side_effect=MercadoPagoError(
            operation="subscription_get",
            endpoint="/preapproval/sub-missing",
            status=404,
            provider_code="not_found",
            provider_message="resource not found",
        ),
    )
    def test_missing_provider_resource_returns_controlled_retry(
        self, _get_subscription
    ):
        payload = self.event(
            "evt-missing-provider", "subscription_preapproval", "sub-missing"
        )
        response = self.signed_webhook(payload, "sub-missing", "request-missing")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["error"], "provider_unavailable")

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

    def create_subscription(self):
        subscription = Subscription(
            user_id=self.user_id,
            provider="mercado_pago",
            provider_subscription_id="sub-101",
            external_reference=f"boost:subscription:{uuid4()}",
            plan="PRO",
            status="pending",
            amount="25.90",
            currency="BRL",
        )
        db.session.add(subscription)
        db.session.commit()
        return subscription

    @staticmethod
    def provider_subscription(subscription, status):
        return {
            "id": subscription.provider_subscription_id,
            "preapproval_plan_id": None,
            "external_reference": subscription.external_reference,
            "status": status,
            "date_created": "2026-08-17T12:00:00Z",
            "next_payment_date": "2026-09-17T12:00:00Z",
            "auto_recurring": {
                "frequency": 1,
                "frequency_type": "months",
                "transaction_amount": "25.90",
                "currency_id": "BRL",
            },
        }

    @staticmethod
    def provider_invoice(subscription, status, invoice_id, payment_id):
        return {
            "id": int(invoice_id),
            "preapproval_id": subscription.provider_subscription_id,
            "external_reference": subscription.external_reference,
            "transaction_amount": "25.90",
            "currency_id": "BRL",
            "date_created": "2026-08-17T11:59:00Z",
            "debit_date": "2026-08-17T12:00:00Z",
            "status": "scheduled",
            "payment": {
                "id": int(payment_id),
                "status": status,
                "status_detail": "accredited" if status == "approved" else status,
            },
        }

    @staticmethod
    def event(event_id, event_type, resource_id):
        return {
            "id": event_id,
            "type": event_type,
            "action": "updated",
            "data": {"id": resource_id},
        }

    @staticmethod
    def gateway(provider_subscription, provider_invoice=None):
        gateway = Mock()
        gateway.get_subscription.return_value = provider_subscription
        gateway.get_authorized_payment.return_value = provider_invoice
        return gateway


if __name__ == "__main__":
    unittest.main()
