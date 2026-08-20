import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from flask import Blueprint, Flask
from flask_login import LoginManager

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = BACKEND_ROOT.parent / "frontend"
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.main.checkout_routes import payments_bp
from Blueprints.main.tools_registry import build_tool_counts
from Blueprints.services.payments.mercado_pago_client import (
    AuthorizedSubscription,
    MercadoPagoError,
)
from extensions import db
from models import Payment, Subscription, Usuario
from security import CSRF_HEADER_NAME, CSRF_SESSION_KEY, init_security


class PaymentCheckoutTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(
            __name__,
            template_folder=str(FRONTEND_ROOT / "templates"),
            static_folder=str(FRONTEND_ROOT / "static"),
        )
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="test-secret-key-with-at-least-32-characters",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            MERCADOPAGO_PUBLIC_KEY="APP_USR-public-key",
            MERCADOPAGO_ACCESS_TOKEN="APP_USR-private-token",
            MERCADOPAGO_WEBHOOK_URL="https://boostconvert.com.br/webhooks/mercado-pago",
            MERCADOPAGO_WEBHOOK_SECRET="webhook-secret",
            MERCADOPAGO_API_BASE_URL="https://api.mercadopago.com",
            MERCADOPAGO_REQUEST_TIMEOUT_SECONDS=10,
            MERCADOPAGO_MAX_INSTALLMENTS=5,
            PRO_PLAN_PRICE="25.90",
            BASE_URL="https://boostconvert.com.br",
            CSRF_ENABLED=True,
            RATE_LIMIT_ENABLED=False,
            FORCE_HTTPS=False,
        )
        db.init_app(self.app)
        login_manager = LoginManager(self.app)

        @login_manager.user_loader
        def load_user(user_id):
            return db.session.get(Usuario, int(user_id))

        init_security(self.app)

        @self.app.context_processor
        def template_globals():
            return {
                "tool_counts": build_tool_counts(),
                "tool_search_index": [],
                "css_version": 1,
                "js_version": 1,
                "favicon_version": 1,
            }

        main = Blueprint("main", __name__)
        main.add_url_rule("/planos", "planos", lambda: "planos")
        home = Blueprint("home", __name__)
        home.add_url_rule("/conta", "conta", lambda: "conta")
        for endpoint in (
            "home",
            "tools",
            "audio_tools",
            "document_tools",
            "guides_index",
            "image_tools",
            "pdf_tools",
            "video_tools",
            "contact_page",
            "privacy_page",
            "security_page",
            "sobre",
            "terms_page",
        ):
            home.add_url_rule(f"/stub/{endpoint}", endpoint, lambda: "stub")
        home.add_url_rule("/stub/converter/<slug>", "converter_tool", lambda slug: slug)
        auth = Blueprint("auth", __name__)
        auth.add_url_rule("/login", "login", lambda: "login")
        auth.add_url_rule("/logout", "logout", lambda: "logout")
        self.app.register_blueprint(main)
        self.app.register_blueprint(home)
        self.app.register_blueprint(auth)
        self.app.register_blueprint(payments_bp)
        with self.app.app_context():
            db.create_all()
            user = Usuario(email="buyer@example.com", nome="Buyer")
            other = Usuario(email="other@example.com", nome="Other")
            db.session.add_all([user, other])
            db.session.commit()
            self.user_id = user.id
            self.other_user_id = other.id
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_checkout_requires_authentication(self):
        self.assertEqual(self.post_checkout().status_code, 401)

    def test_checkout_page_limits_card_brick_to_one_installment(self):
        self.login()
        response = self.client.get("/checkout-pro")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("https://sdk.mercadopago.com/js/v2", body)
        self.assertIn("APP_USR-public-key", body)
        self.assertNotIn("APP_USR-private-token", body)
        self.assertIn('data-max-installments="1"', body)
        self.assertIn("R$ 25,90 / mês", body)

    def test_checkout_creates_authorized_monthly_subscription(self):
        self.login()
        key = str(uuid4())
        with (
            self.provider() as create_subscription,
            patch(
                "Blueprints.services.payments.payment_service.MercadoPagoClient.create_payment"
            ) as create_payment,
        ):
            response = self.post_checkout(
                key=key,
                transaction_amount=1,
                payer={"email": "attacker@example.com"},
            )

        self.assertEqual(response.status_code, 202)
        create_payment.assert_not_called()
        payload = create_subscription.call_args.args[0]
        recurring = payload["auto_recurring"]
        self.assertEqual(payload["reason"], "BoostConvert PRO mensal")
        self.assertEqual(payload["payer_email"], "buyer@example.com")
        self.assertEqual(payload["card_token_id"], "short-lived-token")
        self.assertEqual(payload["status"], "authorized")
        self.assertEqual(
            payload["back_url"], "https://boostconvert.com.br/pagamento/retorno"
        )
        self.assertEqual(recurring["frequency"], 1)
        self.assertEqual(recurring["frequency_type"], "months")
        self.assertEqual(recurring["transaction_amount"], 25.90)
        self.assertEqual(recurring["currency_id"], "BRL")
        self.assertNotIn("installments", payload)
        self.assertNotIn("transaction_amount", payload)
        self.assertNotIn("statement_descriptor", payload)
        self.assertEqual(create_subscription.call_args.kwargs["idempotency_key"], key)
        with self.app.app_context():
            subscription = Subscription.query.one()
            self.assertEqual(
                subscription.external_reference,
                f"boost:subscription:{self.user_id}:{key}",
            )
            self.assertEqual(subscription.provider_subscription_id, "sub-1001")
            self.assertEqual(subscription.status, "active")
            self.assertIsNone(subscription.checkout_url)
            self.assertEqual(Payment.query.count(), 0)
        self.assert_user_free()

    def test_checkout_accepts_payload_without_installments(self):
        self.login()
        with self.provider() as create_subscription:
            response = self.post_checkout(include_installments=False)
        self.assertEqual(response.status_code, 202)
        self.assertNotIn("installments", create_subscription.call_args.args[0])

    def test_more_than_one_installment_is_rejected_before_subscription_creation(self):
        self.login()
        with patch(
            "Blueprints.services.payments.payment_service.MercadoPagoClient.create_authorized_subscription"
        ) as create_subscription:
            response = self.post_checkout(installments=2)
        self.assertEqual(response.status_code, 400)
        create_subscription.assert_not_called()

    def test_authorized_subscription_does_not_activate_pro_without_paid_invoice(self):
        self.login()
        with self.provider(status="authorized"):
            response = self.post_checkout()
        self.assertFalse(response.json["approved"])
        self.assertEqual(response.json["status"], "active")
        self.assert_user_free()

    def test_same_key_creates_only_one_provider_subscription(self):
        self.login()
        key = str(uuid4())
        with self.provider() as create_subscription:
            first = self.post_checkout(key=key)
            second = self.post_checkout(key=key, token="another-short-lived-token")
        self.assertEqual((first.status_code, second.status_code), (202, 202))
        create_subscription.assert_called_once()
        with self.app.app_context():
            self.assertEqual(Subscription.query.count(), 1)
            self.assertEqual(Payment.query.count(), 0)

    def test_invalid_idempotency_key_is_rejected_before_provider(self):
        self.login()
        with patch(
            "Blueprints.services.payments.payment_service.MercadoPagoClient.create_authorized_subscription"
        ) as create_subscription:
            response = self.post_checkout(key="not-a-uuid")
        self.assertEqual(response.status_code, 400)
        create_subscription.assert_not_called()

    def test_debit_card_is_rejected_before_subscription_creation(self):
        self.login()
        with (
            patch(
                "Blueprints.services.payments.payment_service.MercadoPagoClient.get_payment_methods",
                return_value=[
                    {"id": "visa", "payment_type_id": "debit_card", "status": "active"}
                ],
            ),
            patch(
                "Blueprints.services.payments.payment_service.MercadoPagoClient.create_authorized_subscription"
            ) as create_subscription,
        ):
            response = self.post_checkout()
        self.assertEqual(response.status_code, 400)
        create_subscription.assert_not_called()

    def test_provider_failure_preserves_subscription_without_sensitive_logs(self):
        self.login()
        sensitive_token = "card-token-must-not-appear"
        error = MercadoPagoError(
            operation="subscription_create",
            endpoint="/preapproval",
            status=503,
            provider_code="service_unavailable",
            provider_message="temporary failure",
        )
        with (
            patch(
                "Blueprints.services.payments.payment_service.MercadoPagoClient.get_payment_methods",
                return_value=self.credit_methods(),
            ),
            patch(
                "Blueprints.services.payments.payment_service.MercadoPagoClient.create_authorized_subscription",
                side_effect=error,
            ),
            self.assertLogs(self.app.logger.name, level="WARNING") as logs,
        ):
            response = self.post_checkout(token=sensitive_token)
        output = " ".join(logs.output)
        self.assertEqual(response.status_code, 502)
        self.assertIn("mercadopago_subscription_create_failed", output)
        self.assertIn("operation=subscription_create", output)
        self.assertIn("endpoint=/preapproval", output)
        self.assertNotIn(sensitive_token, output)
        self.assertNotIn("temporary failure", response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(Subscription.query.one().status, "error")
            self.assertEqual(Payment.query.count(), 0)

    def test_card_token_and_card_number_are_never_persisted(self):
        self.login()
        token = "short-lived-card-token"
        with self.provider():
            self.post_checkout(token=token)
        with self.app.app_context():
            values = " ".join(
                str(value)
                for value in vars(Subscription.query.one()).values()
                if value is not None
            )
        self.assertNotIn(token, values)
        self.assertNotIn("4111111111111111", values)

    def test_subscription_status_reconciles_approved_invoice_and_activates_pro(self):
        self.login()
        key = str(uuid4())
        with self.provider():
            created = self.post_checkout(key=key)
        self.assertEqual(created.status_code, 202)
        with self.app.app_context():
            subscription = Subscription.query.one()
            remote_subscription = self.remote_subscription(subscription)
            remote_invoice = self.remote_invoice(subscription, status="approved")
        with (
            patch(
                "Blueprints.services.payments.payment_service.MercadoPagoClient.get_subscription",
                return_value=remote_subscription,
            ),
            patch(
                "Blueprints.services.payments.payment_service.MercadoPagoClient.search_authorized_payments",
                return_value=[remote_invoice],
            ),
        ):
            response = self.client.get(f"/api/subscriptions/{key}/status")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["approved"])
        self.assertEqual(response.json["status"], "approved")
        with self.app.app_context():
            payment = Payment.query.one()
            self.assertEqual(payment.payment_method, "recurring_subscription")
            self.assertEqual(payment.provider_invoice_id, "501")
        self.assert_user_pro()

    def test_subscription_status_cannot_read_another_users_attempt(self):
        with self.app.app_context():
            subscription = self.local_subscription(self.other_user_id)
            attempt_id = subscription.checkout_idempotency_key
        self.login()
        self.assertEqual(
            self.client.get(f"/api/subscriptions/{attempt_id}/status").status_code,
            404,
        )

    def test_active_legacy_entitlement_blocks_duplicate_subscription(self):
        with self.app.app_context():
            subscription = self.local_subscription(self.user_id, status="active")
            subscription.paid_through_at = datetime.now(timezone.utc) + timedelta(
                days=10
            )
            remote = self.remote_subscription(subscription)
            db.session.commit()
        self.login()
        with (
            patch(
                "Blueprints.services.payments.payment_service.MercadoPagoClient.get_subscription",
                return_value=remote,
            ),
            patch(
                "Blueprints.services.payments.payment_service.MercadoPagoClient.search_authorized_payments",
                return_value=[],
            ),
            patch(
                "Blueprints.services.payments.payment_service.MercadoPagoClient.create_authorized_subscription"
            ) as create_subscription,
        ):
            response = self.post_checkout()
        self.assertEqual(response.status_code, 409)
        create_subscription.assert_not_called()

    def test_canceling_subscription_keeps_valid_legacy_payment_access(self):
        with self.app.app_context():
            payment = self.local_payment(self.user_id, status="approved")
            payment.provider_payment_id = "1000099"
            payment.premium_expires_at = datetime.now(timezone.utc) + timedelta(days=20)
            subscription = self.local_subscription(self.user_id, status="active")
            subscription_id = subscription.provider_subscription_id
            reference = subscription.external_reference
            db.session.commit()
        self.login()
        with patch(
            "Blueprints.services.payments.payment_service.MercadoPagoClient.cancel_subscription",
            return_value={
                "id": subscription_id,
                "external_reference": reference,
                "status": "cancelled",
            },
        ):
            response = self.client.post(
                "/api/subscriptions/cancel", headers=self.csrf_headers()
            )
        self.assertEqual(response.status_code, 200)
        self.assert_user_pro()

    def test_legacy_payment_status_endpoint_remains_available(self):
        with self.app.app_context():
            payment = self.local_payment(self.user_id)
            attempt_id = payment.attempt_id
        self.login()
        response = self.client.get(f"/api/payments/{attempt_id}/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["attempt_id"], attempt_id)

    def test_frontend_contract_is_card_brick_credit_only_and_one_installment(self):
        script = (FRONTEND_ROOT / "static" / "js" / "payments.js").read_text(
            encoding="utf-8"
        )
        templates = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (FRONTEND_ROOT / "templates").rglob("*.html")
        )
        self.assertIn('bricksBuilder.create("cardPayment"', script)
        self.assertIn('excluded: ["debit_card", "prepaid_card"]', script)
        self.assertIn(
            "Math.min(Number(config.dataset.maxInstallments || 1), 1)", script
        )
        self.assertNotIn("installments:", script)
        self.assertIn('"X-Idempotency-Key": idempotencyKey', script)
        self.assertIn("cardSubmissionInFlight", script)
        self.assertNotIn("MERCADOPAGO_ACCESS_TOKEN", script + templates)
        self.assertNotIn("subscriptions/checkout", script + templates)
        self.assertNotIn("result.checkout_url", script)

    def provider(self, *, status="authorized", subscription_id="sub-1001"):
        create_patch = patch(
            "Blueprints.services.payments.payment_service.MercadoPagoClient.create_authorized_subscription",
            return_value=AuthorizedSubscription(subscription_id, status),
        )
        methods_patch = patch(
            "Blueprints.services.payments.payment_service.MercadoPagoClient.get_payment_methods",
            return_value=self.credit_methods(),
        )
        create_subscription = create_patch.start()
        methods_patch.start()
        self.addCleanup(create_patch.stop)
        self.addCleanup(methods_patch.stop)
        return _MockContext(create_subscription)

    @staticmethod
    def credit_methods():
        return [{"id": "visa", "payment_type_id": "credit_card", "status": "active"}]

    @staticmethod
    def remote_subscription(subscription):
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
            "date_created": datetime.now(timezone.utc).isoformat(),
            "next_payment_date": (
                datetime.now(timezone.utc) + timedelta(days=30)
            ).isoformat(),
        }

    @staticmethod
    def remote_invoice(subscription, status="pending"):
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

    def local_subscription(self, user_id, status="pending"):
        attempt_id = str(uuid4())
        subscription = Subscription(
            user_id=user_id,
            provider="mercado_pago",
            provider_subscription_id=f"sub-{attempt_id}",
            external_reference=f"boost:subscription:{user_id}:{attempt_id}",
            checkout_idempotency_key=attempt_id,
            plan="PRO",
            status=status,
            amount="25.90",
            currency="BRL",
        )
        db.session.add(subscription)
        db.session.commit()
        return subscription

    def local_payment(self, user_id, status="pending"):
        attempt_id = str(uuid4())
        payment = Payment(
            user_id=user_id,
            provider="mercado_pago",
            external_reference=f"boost:payment:{user_id}:{attempt_id}",
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

    def post_checkout(self, key=None, include_installments=True, **overrides):
        payload = {
            "token": overrides.pop("token", "short-lived-token"),
            "payment_method_id": "visa",
            "issuer_id": "123",
            "payer": {"email": "browser@example.com"},
            **overrides,
        }
        if include_installments and "installments" not in payload:
            payload["installments"] = 1
        return self.client.post(
            "/api/payments/checkout",
            json=payload,
            headers={
                **self.csrf_headers(),
                "X-Idempotency-Key": key or str(uuid4()),
            },
        )

    def login(self):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user_id)
            session["_fresh"] = True

    def csrf_headers(self):
        token = "test-csrf-token-with-enough-length-123"
        with self.client.session_transaction() as session:
            session[CSRF_SESSION_KEY] = token
        return {CSRF_HEADER_NAME: token, "Accept": "application/json"}

    def assert_user_free(self):
        with self.app.app_context():
            user = db.session.get(Usuario, self.user_id)
            self.assertEqual((user.plano, user.status_assinatura), ("free", "inactive"))

    def assert_user_pro(self):
        with self.app.app_context():
            user = db.session.get(Usuario, self.user_id)
            self.assertEqual((user.plano, user.status_assinatura), ("pro", "active"))


class _MockContext:
    def __init__(self, mock):
        self.mock = mock

    def __enter__(self):
        return self.mock

    def __exit__(self, *_args):
        return False


if __name__ == "__main__":
    unittest.main()
