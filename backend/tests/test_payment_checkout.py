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
from Blueprints.services.payments.mercado_pago_client import MercadoPagoError
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
            MERCADOPAGO_MAX_INSTALLMENTS=12,
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
        home.add_url_rule(
            "/stub/converter/<slug>",
            "converter_tool",
            lambda slug: slug,
        )
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
        self.assertEqual(self.post_payment().status_code, 401)

    def test_checkout_page_renders_card_brick_with_public_key_only(self):
        self.login()
        response = self.client.get("/checkout-pro")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("https://sdk.mercadopago.com/js/v2", body)
        self.assertIn("APP_USR-public-key", body)
        self.assertNotIn("APP_USR-private-token", body)
        self.assertIn("cardPaymentBrick_container", body)

    def test_approved_payment_uses_server_amount_email_and_idempotency(self):
        self.login()
        with self.provider(status="approved") as create_payment:
            key = str(uuid4())
            response = self.post_payment(
                key=key,
                transaction_amount=1,
                payer={"email": "attacker@example.com"},
            )
        self.assertEqual(response.status_code, 201)
        payload = create_payment.call_args.args[0]
        self.assertEqual(payload["transaction_amount"], 25.90)
        self.assertEqual(payload["payer"]["email"], "buyer@example.com")
        self.assertEqual(create_payment.call_args.kwargs["idempotency_key"], key)
        self.assertTrue(response.json["approved"])
        with self.app.app_context():
            payment = Payment.query.one()
            user = db.session.get(Usuario, self.user_id)
            self.assertEqual(str(payment.amount), "25.90")
            self.assertEqual((user.plano, user.status_assinatura), ("pro", "active"))
            self.assertIsNotNone(payment.premium_expires_at)

    def test_external_reference_and_metadata_correlate_attempt(self):
        self.login()
        key = str(uuid4())
        with self.provider() as create_payment:
            response = self.post_payment(key=key)
        payload = create_payment.call_args.args[0]
        self.assertEqual(response.status_code, 202)
        self.assertEqual(payload["metadata"]["attempt_id"], key)
        self.assertEqual(payload["metadata"]["user_id"], self.user_id)
        self.assertEqual(payload["metadata"]["plan"], "PRO")
        self.assertEqual(
            payload["external_reference"], f"boost:payment:{self.user_id}:{key}"
        )

    def test_pending_payment_does_not_activate_pro(self):
        self.login()
        with self.provider(status="pending"):
            response = self.post_payment()
        self.assertEqual(response.status_code, 202)
        self.assertFalse(response.json["approved"])
        self.assert_user_free()

    def test_in_process_payment_does_not_activate_pro(self):
        self.login()
        with self.provider(status="in_process"):
            response = self.post_payment()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json["status"], "in_process")
        self.assert_user_free()

    def test_rejected_payment_does_not_activate_pro(self):
        self.login()
        with self.provider(status="rejected"):
            response = self.post_payment()
        self.assertEqual(response.status_code, 422)
        self.assertIn("Pagamento recusado", response.json["error"])
        self.assert_user_free()

    def test_invalid_idempotency_key_is_rejected_before_provider(self):
        self.login()
        with patch(
            "Blueprints.services.payments.payment_service.MercadoPagoClient.create_payment"
        ) as create_payment:
            response = self.post_payment(key="not-a-uuid")
        self.assertEqual(response.status_code, 400)
        create_payment.assert_not_called()

    def test_debit_card_is_rejected_before_payment_creation(self):
        self.login()
        with (
            patch(
                "Blueprints.services.payments.payment_service.MercadoPagoClient.get_payment_methods",
                return_value=[
                    {"id": "visa", "payment_type_id": "debit_card", "status": "active"}
                ],
            ),
            patch(
                "Blueprints.services.payments.payment_service.MercadoPagoClient.create_payment"
            ) as create_payment,
        ):
            response = self.post_payment()
        self.assertEqual(response.status_code, 400)
        create_payment.assert_not_called()

    def test_same_key_creates_only_one_provider_payment(self):
        self.login()
        key = str(uuid4())
        with self.provider() as create_payment:
            first = self.post_payment(key=key)
            second = self.post_payment(key=key, token="another-short-lived-token")
        self.assertEqual((first.status_code, second.status_code), (202, 202))
        create_payment.assert_called_once()
        with self.app.app_context():
            self.assertEqual(Payment.query.count(), 1)

    def test_provider_failure_preserves_attempt_without_sensitive_logs(self):
        self.login()
        sensitive_token = "card-token-must-not-appear"
        error = MercadoPagoError(
            operation="payment_create",
            endpoint="/v1/payments",
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
                "Blueprints.services.payments.payment_service.MercadoPagoClient.create_payment",
                side_effect=error,
            ),
            self.assertLogs(self.app.logger.name, level="WARNING") as logs,
        ):
            response = self.post_payment(token=sensitive_token)
        self.assertEqual(response.status_code, 502)
        self.assertNotIn(sensitive_token, " ".join(logs.output))
        self.assertNotIn("temporary failure", response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(Payment.query.one().status, "creating")

    def test_provider_wrong_amount_fails_closed(self):
        self.login()
        with self.provider(amount="1.00"):
            response = self.post_payment()
        self.assertEqual(response.status_code, 502)
        self.assert_user_free()

    def test_card_token_and_card_number_are_never_persisted(self):
        self.login()
        token = "short-lived-card-token"
        with self.provider():
            self.post_payment(token=token)
        with self.app.app_context():
            values = " ".join(
                str(value)
                for value in vars(Payment.query.one()).values()
                if value is not None
            )
        self.assertNotIn(token, values)
        self.assertNotIn("4111111111111111", values)

    def test_status_endpoint_reconciles_pending_to_approved(self):
        self.login()
        with self.provider(status="pending"):
            created = self.post_payment()
        attempt_id = created.json["attempt_id"]
        with self.app.app_context():
            payment = Payment.query.filter_by(attempt_id=attempt_id).one()
            payment.last_provider_sync_at = datetime.now(timezone.utc) - timedelta(
                minutes=1
            )
            db.session.commit()
        with patch(
            "Blueprints.services.payments.payment_service.MercadoPagoClient.get_payment",
            return_value=self.remote_payment(
                attempt_id, self.user_id, status="approved"
            ),
        ):
            response = self.client.get(f"/api/payments/{attempt_id}/status")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["approved"])
        self.assert_user_pro()

    def test_status_endpoint_cannot_read_another_users_payment(self):
        with self.app.app_context():
            payment = self.local_payment(self.other_user_id)
            attempt_id = payment.attempt_id
        self.login()
        self.assertEqual(
            self.client.get(f"/api/payments/{attempt_id}/status").status_code,
            404,
        )

    def test_early_renewal_preserves_remaining_days(self):
        self.login()
        existing_expiration = datetime.now(timezone.utc) + timedelta(days=10)
        with self.app.app_context():
            existing = self.local_payment(self.user_id, status="approved")
            existing.provider_payment_id = "1000001"
            existing.premium_expires_at = existing_expiration
            db.session.commit()
        with self.provider(status="approved", payment_id="1000002"):
            self.post_payment()
        with self.app.app_context():
            newest = Payment.query.filter_by(provider_payment_id="1000002").one()
            difference = (
                newest.premium_expires_at.replace(tzinfo=timezone.utc)
                - existing_expiration
            )
            self.assertAlmostEqual(difference.total_seconds(), 30 * 86400, delta=2)

    def test_refunded_payment_removes_access(self):
        self.login()
        with self.provider(status="approved"):
            created = self.post_payment()
        attempt_id = created.json["attempt_id"]
        with self.app.app_context():
            payment_id = (
                Payment.query.filter_by(attempt_id=attempt_id).one().provider_payment_id
            )
        with patch(
            "Blueprints.services.payments.payment_service.MercadoPagoClient.get_payment",
            return_value=self.remote_payment(
                attempt_id, self.user_id, status="refunded", payment_id=payment_id
            ),
        ):
            with self.app.app_context():
                payment = Payment.query.filter_by(attempt_id=attempt_id).one()
                payment.status = "pending"
                payment.last_provider_sync_at = datetime.now(timezone.utc) - timedelta(
                    minutes=1
                )
                db.session.commit()
            response = self.client.get(f"/api/payments/{attempt_id}/status")
        self.assertEqual(response.json["status"], "refunded")
        self.assert_user_free()

    def test_legacy_subscription_does_not_block_new_one_time_payment(self):
        with self.app.app_context():
            db.session.add(
                Subscription(
                    user_id=self.user_id,
                    provider="mercado_pago",
                    provider_subscription_id="legacy-sub",
                    external_reference="boost:subscription:legacy",
                    status="pending",
                )
            )
            db.session.commit()
        self.login()
        with self.provider():
            response = self.post_payment()
        self.assertEqual(response.status_code, 202)
        with self.app.app_context():
            self.assertEqual(Subscription.query.count(), 1)
            self.assertEqual(Payment.query.count(), 1)

    def test_canceling_legacy_subscription_keeps_valid_payment_access(self):
        with self.app.app_context():
            payment = self.local_payment(self.user_id, status="approved")
            payment.provider_payment_id = "1000099"
            payment.premium_expires_at = datetime.now(timezone.utc) + timedelta(days=20)
            subscription = Subscription(
                user_id=self.user_id,
                provider="mercado_pago",
                provider_subscription_id="legacy-active",
                external_reference="boost:subscription:legacy-active",
                status="active",
            )
            db.session.add(subscription)
            db.session.commit()
        self.login()
        with patch(
            "Blueprints.services.payments.payment_service.MercadoPagoClient.cancel_subscription",
            return_value={
                "id": "legacy-active",
                "external_reference": "boost:subscription:legacy-active",
                "status": "cancelled",
            },
        ):
            response = self.client.post(
                "/api/subscriptions/cancel", headers=self.csrf_headers()
            )
        self.assertEqual(response.status_code, 200)
        self.assert_user_pro()

    def test_frontend_contract_is_card_brick_credit_only(self):
        script = (FRONTEND_ROOT / "static" / "js" / "payments.js").read_text(
            encoding="utf-8"
        )
        templates = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (FRONTEND_ROOT / "templates").rglob("*.html")
        )
        self.assertIn('bricksBuilder.create("cardPayment"', script)
        self.assertIn('excluded: ["debit_card", "prepaid_card"]', script)
        self.assertIn('"X-Idempotency-Key": idempotencyKey', script)
        self.assertIn("cardSubmissionInFlight", script)
        self.assertNotIn("MERCADOPAGO_ACCESS_TOKEN", script + templates)
        self.assertNotIn("subscriptions/checkout", script + templates)
        self.assertNotIn("result.checkout_url", script)

    def provider(self, **overrides):
        create_patch = patch(
            "Blueprints.services.payments.payment_service.MercadoPagoClient.create_payment"
        )
        methods_patch = patch(
            "Blueprints.services.payments.payment_service.MercadoPagoClient.get_payment_methods",
            return_value=self.credit_methods(),
        )
        create_payment = create_patch.start()
        methods_patch.start()

        def response(payload, *, idempotency_key):
            return self.remote_payment(
                idempotency_key,
                self.user_id,
                external_reference=payload["external_reference"],
                payment_method_id=payload["payment_method_id"],
                **overrides,
            )

        create_payment.side_effect = response
        self.addCleanup(create_patch.stop)
        self.addCleanup(methods_patch.stop)
        return _MockContext(create_payment)

    @staticmethod
    def credit_methods():
        return [{"id": "visa", "payment_type_id": "credit_card", "status": "active"}]

    @staticmethod
    def remote_payment(
        attempt_id,
        user_id,
        *,
        status="pending",
        amount="25.90",
        payment_id="1000001",
        external_reference=None,
        payment_method_id="visa",
    ):
        return {
            "id": int(payment_id),
            "status": status,
            "status_detail": "accredited" if status == "approved" else status,
            "transaction_amount": amount,
            "currency_id": "BRL",
            "payment_method_id": payment_method_id,
            "payment_type_id": "credit_card",
            "external_reference": external_reference
            or f"boost:payment:{user_id}:{attempt_id}",
            "metadata": {
                "user_id": user_id,
                "plan": "PRO",
                "attempt_id": attempt_id,
            },
            "date_created": datetime.now(timezone.utc).isoformat(),
            "date_approved": datetime.now(timezone.utc).isoformat(),
        }

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

    def post_payment(self, key=None, **overrides):
        payload = {
            "token": overrides.pop("token", "short-lived-token"),
            "payment_method_id": "visa",
            "issuer_id": "123",
            "installments": 1,
            "payer": {"email": "browser@example.com"},
            **overrides,
        }
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
