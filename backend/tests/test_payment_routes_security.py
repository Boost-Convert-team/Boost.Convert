import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from flask_login import LoginManager
from sqlalchemy.exc import OperationalError


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.main.checkout_routes import checkout_bp
from Blueprints.services.subscription.mercado_pago_payments_service import (
    IdempotencyKeyValidationError,
)
from Blueprints.services.subscription.mercado_pago_service import (
    MercadoPagoHTTPError,
    MercadoPagoInvalidResponseError,
    MercadoPagoTimeoutError,
)
from extensions import db
from models import Payment, Usuario
from security import CSRF_HEADER_NAME, CSRF_SESSION_KEY, clear_rate_limit_state, init_security


class PaymentRouteSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_rate_limit_state()
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="test-secret-key-with-at-least-32-characters",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            FORCE_HTTPS=False,
            CSRF_ENABLED=True,
            RATE_LIMIT_ENABLED=True,
            MERCADO_PAGO_ENVIRONMENT="test",
            MERCADO_PAGO_ACCESS_TOKEN="TEST-fake-token",
            MERCADO_PAGO_PLAN_PRICE="19.90",
        )
        db.init_app(self.app)
        login_manager = LoginManager()
        login_manager.init_app(self.app)

        @login_manager.user_loader
        def load_user(user_id):
            return db.session.get(Usuario, int(user_id))

        init_security(self.app)
        self.app.register_blueprint(checkout_bp)
        with self.app.app_context():
            db.create_all()
            user = Usuario(email="route-card@example.com", plano="free", status_assinatura="inactive")
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_card_endpoint_requires_authentication(self) -> None:
        response = self.client.post(
            "/api/payment/card",
            json=self.card_payload(),
            headers=self.csrf_headers(),
        )
        self.assertEqual(response.status_code, 401)

    def test_card_endpoint_requires_csrf_even_when_authenticated(self) -> None:
        self.login()
        with patch(
            "Blueprints.main.checkout_routes.create_mercado_pago_card_payment"
        ) as service:
            response = self.client.post("/api/payment/card", json=self.card_payload())
        self.assertEqual(response.status_code, 400)
        service.assert_not_called()

    def test_pix_endpoint_requires_csrf_even_when_authenticated(self) -> None:
        self.login()
        with patch(
            "Blueprints.main.checkout_routes.create_mercado_pago_pix_payment"
        ) as service:
            response = self.client.post(
                "/api/payment/pix",
                data={
                    "pix_idempotency_key": "11111111-2222-4333-8444-555555555555"
                },
            )
        self.assertEqual(response.status_code, 400)
        service.assert_not_called()

    def test_card_endpoint_accepts_only_json_and_uuid_idempotency(self) -> None:
        self.login()
        headers = self.csrf_headers()
        non_json = self.client.post(
            "/api/payment/card",
            data={"token": "tok"},
            headers=headers,
        )
        self.assertEqual(non_json.status_code, 415)

        with patch(
            "Blueprints.main.checkout_routes.create_mercado_pago_card_payment",
            side_effect=IdempotencyKeyValidationError(
                "X-Idempotency-Key UUID e obrigatorio."
            ),
        ):
            missing_key = self.client.post(
                "/api/payment/card",
                json=self.card_payload(),
                headers=headers,
            )
        self.assertEqual(missing_key.status_code, 400)

    def test_card_endpoint_passes_tokenized_whitelist_and_security_headers(self) -> None:
        self.login()
        response_data = {
            "ok": True,
            "attempt_id": "11111111-2222-4333-8444-555555555555",
            "payment_id": "pay_card_route",
            "status": "pending",
            "approved": False,
        }
        headers = {
            **self.csrf_headers(),
            "X-Idempotency-Key": "11111111-2222-4333-8444-555555555555",
        }
        with patch(
            "Blueprints.main.checkout_routes.create_mercado_pago_card_payment",
            return_value=response_data,
        ) as service:
            response = self.client.post(
                "/api/payment/card", json=self.card_payload(), headers=headers
            )

        self.assertEqual(response.status_code, 202)
        service.assert_called_once()
        self.assertEqual(service.call_args.args[2], headers["X-Idempotency-Key"])
        self.assertIn("mercadopago.com", response.headers["Content-Security-Policy"])
        self.assertNotIn("token", response.get_data(as_text=True))

    def test_database_error_is_rolled_back_and_returns_503(self) -> None:
        self.login()
        headers = {
            **self.csrf_headers(),
            "X-Idempotency-Key": "11111111-2222-4333-8444-555555555555",
        }
        error = OperationalError("SELECT", {}, Exception("payments missing"))
        with patch(
            "Blueprints.main.checkout_routes.create_mercado_pago_card_payment",
            side_effect=error,
        ), patch("Blueprints.main.checkout_routes.db.session.rollback") as rollback:
            response = self.client.post(
                "/api/payment/card", json=self.card_payload(), headers=headers
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["ok"], False)
        self.assertNotIn("payments missing", response.get_data(as_text=True))
        rollback.assert_called_once()

    def test_missing_payments_table_returns_safe_503_without_provider_post(self) -> None:
        self.login()
        with self.app.app_context():
            Payment.__table__.drop(db.engine)
        headers = {
            **self.csrf_headers(),
            "X-Idempotency-Key": "11111111-2222-4333-8444-555555555555",
        }
        with patch(
            "Blueprints.services.subscription.mercado_pago_payments_service.mercado_pago_request",
            return_value=[
                {"id": "visa", "payment_type_id": "credit_card", "status": "active"}
            ],
        ) as provider_request:
            response = self.client.post(
                "/api/payment/card", json=self.card_payload(), headers=headers
            )
        self.assertEqual(response.status_code, 503)
        self.assertIn("temporariamente indisponiveis", response.json["error"])
        self.assertEqual(provider_request.call_count, 1)
        self.assertEqual(provider_request.call_args.args[:2], ("GET", "/v1/payment_methods"))

    def test_provider_rate_limit_returns_503_and_safe_retry_after(self) -> None:
        self.login()
        headers = {
            **self.csrf_headers(),
            "X-Idempotency-Key": "11111111-2222-4333-8444-555555555555",
        }
        error = MercadoPagoHTTPError(
            "Mercado Pago esta temporariamente limitando requisicoes.",
            provider_status=429,
            public_status=503,
            retry_after="30",
        )
        with patch(
            "Blueprints.main.checkout_routes.create_mercado_pago_card_payment",
            side_effect=error,
        ):
            response = self.client.post(
                "/api/payment/card", json=self.card_payload(), headers=headers
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["Retry-After"], "30")

    def test_provider_timeout_422_5xx_and_invalid_json_are_mapped(self) -> None:
        self.login()
        headers = {
            **self.csrf_headers(),
            "X-Idempotency-Key": "11111111-2222-4333-8444-555555555555",
        }
        cases = (
            (MercadoPagoTimeoutError("Mercado Pago demorou para responder."), 503),
            (
                MercadoPagoHTTPError(
                    "Mercado Pago recusou os dados do pagamento.",
                    provider_status=422,
                    public_status=422,
                ),
                422,
            ),
            (
                MercadoPagoHTTPError(
                    "Mercado Pago esta temporariamente indisponivel.",
                    provider_status=500,
                    public_status=503,
                ),
                503,
            ),
            (
                MercadoPagoInvalidResponseError(
                    "Mercado Pago retornou uma resposta invalida."
                ),
                502,
            ),
        )
        for error, expected_status in cases:
            with self.subTest(error=type(error).__name__), patch(
                "Blueprints.main.checkout_routes.create_mercado_pago_card_payment",
                side_effect=error,
            ):
                response = self.client.post(
                    "/api/payment/card", json=self.card_payload(), headers=headers
                )
                self.assertEqual(response.status_code, expected_status)
                self.assertNotIn("traceback", response.get_data(as_text=True).lower())

    def test_user_cannot_reconcile_another_users_payment(self) -> None:
        with self.app.app_context():
            other = Usuario(email="other@example.com", plano="free", status_assinatura="inactive")
            db.session.add(other)
            db.session.flush()
            attempt_id = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
            db.session.add(
                Payment(
                    user_id=other.id,
                    attempt_id=attempt_id,
                    provider_payment_id="pay_other_user",
                    external_reference=f"boost:payment:{attempt_id}:user:{other.id}",
                    payment_method="credit_card",
                    status="pending",
                    amount="19.90",
                    currency="BRL",
                )
            )
            db.session.commit()
        self.login()
        with patch("Blueprints.main.checkout_routes.reconcile_payment") as reconcile:
            response = self.client.get(f"/api/payment/card/{attempt_id}/status")
        self.assertEqual(response.status_code, 404)
        reconcile.assert_not_called()

    def test_card_endpoint_rate_limit_blocks_sixth_attempt(self) -> None:
        self.login()
        headers = {
            **self.csrf_headers(),
            "X-Idempotency-Key": "11111111-2222-4333-8444-555555555555",
        }
        response_data = {
            "ok": True,
            "attempt_id": "11111111-2222-4333-8444-555555555555",
            "payment_id": "pay_rate_limited",
            "status": "pending",
            "approved": False,
        }
        with patch(
            "Blueprints.main.checkout_routes.create_mercado_pago_card_payment",
            return_value=response_data,
        ) as service:
            responses = [
                self.client.post(
                    "/api/payment/card", json=self.card_payload(), headers=headers
                )
                for _index in range(6)
            ]
        self.assertEqual(responses[-1].status_code, 429)
        self.assertEqual(service.call_count, 5)

    def test_pix_endpoint_rate_limit_blocks_sixth_attempt(self) -> None:
        self.login()
        response_data = {
            "ok": True,
            "attempt_id": "11111111-2222-4333-8444-555555555555",
            "payment_id": "pay_pix_rate_limited",
            "status": "pending",
            "approved": False,
        }
        with patch(
            "Blueprints.main.checkout_routes.create_mercado_pago_pix_payment",
            return_value=response_data,
        ) as service:
            responses = [
                self.client.post(
                    "/api/payment/pix",
                    data=self.pix_form(),
                    environ_overrides={"REMOTE_ADDR": "203.0.113.10"},
                )
                for _index in range(6)
            ]
        self.assertEqual(responses[-1].status_code, 429)
        self.assertEqual(service.call_count, 5)

    def test_authenticated_users_do_not_share_pix_rate_limit_by_ip(self) -> None:
        with self.app.app_context():
            other = Usuario(
                email="second-rate-user@example.com",
                plano="free",
                status_assinatura="inactive",
            )
            db.session.add(other)
            db.session.commit()
            other_user_id = other.id

        response_data = {
            "ok": True,
            "attempt_id": "11111111-2222-4333-8444-555555555555",
            "payment_id": "pay_pix_shared_ip",
            "status": "pending",
            "approved": False,
        }
        with patch(
            "Blueprints.main.checkout_routes.create_mercado_pago_pix_payment",
            return_value=response_data,
        ) as service:
            self.login()
            first_user_responses = [
                self.client.post(
                    "/api/payment/pix",
                    data=self.pix_form(),
                    environ_overrides={"REMOTE_ADDR": "203.0.113.20"},
                )
                for _index in range(5)
            ]
            self.login(other_user_id)
            second_user_response = self.client.post(
                "/api/payment/pix",
                data=self.pix_form(),
                environ_overrides={"REMOTE_ADDR": "203.0.113.20"},
            )

        self.assertTrue(all(response.status_code == 201 for response in first_user_responses))
        self.assertEqual(second_user_response.status_code, 201)
        self.assertEqual(service.call_count, 6)

    def login(self, user_id: int | None = None) -> None:
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user_id or self.user_id)
            session["_fresh"] = True

    def csrf_headers(self) -> dict[str, str]:
        token = "test-csrf-token-with-enough-length-123"
        with self.client.session_transaction() as session:
            session[CSRF_SESSION_KEY] = token
        return {CSRF_HEADER_NAME: token}

    @staticmethod
    def card_payload() -> dict:
        return {
            "token": "tok_test_route",
            "payment_method_id": "visa",
            "issuer_id": "123",
            "installments": 1,
            "payer": {"email": "route-card@example.com"},
        }

    def pix_form(self) -> dict[str, str]:
        token = "test-csrf-token-with-enough-length-123"
        with self.client.session_transaction() as session:
            session[CSRF_SESSION_KEY] = token
        return {
            "_csrf_token": token,
            "pix_idempotency_key": "11111111-2222-4333-8444-555555555555",
        }


if __name__ == "__main__":
    unittest.main()
