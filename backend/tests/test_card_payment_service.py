import sys
import unittest
from datetime import timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from flask import Flask


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.subscription.mercado_pago_payments_service import (
    CardPaymentValidationError,
    create_card_payment,
    get_or_create_payment_attempt,
    reconcile_payment,
)
from Blueprints.services.subscription.mercado_pago_service import MercadoPagoError
from extensions import db
from models import Payment, Usuario


class CardPaymentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            MERCADO_PAGO_ACCESS_TOKEN="TEST-token",
            MERCADO_PAGO_PLAN_PRICE="19.90",
            MERCADO_PAGO_ENVIRONMENT="test",
            MERCADO_PAGO_COLLECTOR_ID="123456",
            MERCADO_PAGO_MAX_INSTALLMENTS=12,
            BASE_URL="https://boostconvert.com.br",
        )
        db.init_app(self.app)
        with self.app.app_context():
            db.create_all()

    def tearDown(self) -> None:
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_approved_credit_card_grants_exactly_30_days(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/api/payment/card", method="POST"):
            user = self.create_user("card@example.com")
            posted_payload = {}

            def provider_request(method, path, **kwargs):
                if path == "/v1/payment_methods":
                    return [self.credit_method()]
                if path.startswith("/v1/payments/search?"):
                    return {"results": []}
                if method == "POST":
                    posted_payload.update(kwargs["json_payload"])
                    return self.provider_card_data("pay_card_1", kwargs["json_payload"], "approved")
                return self.provider_card_data("pay_card_1", posted_payload, "approved")

            with patch(
                "Blueprints.services.subscription.mercado_pago_payments_service.mercado_pago_request",
                side_effect=provider_request,
            ):
                result = create_card_payment(
                    user,
                    self.card_request(transaction_amount="0.01"),
                    "11111111-2222-4333-8444-555555555555",
                )

            payment = Payment.query.one()
            self.assertFalse(result["approved"])
            self.assertEqual((user.plano, user.status_assinatura), ("free", "inactive"))
            self.assertIsNone(payment.premium_expires_at)
            self.assertEqual(payment.payment_method, "credit_card")
            self.assertEqual(payment.payment_method, "credit_card")
            self.assertEqual(posted_payload["transaction_amount"], 19.90)
            self.assertNotIn("token", Payment.__table__.columns.keys())
            self.assertNotIn("tok_test_123", repr(payment.__dict__))

            verified = self.provider_card_data("pay_card_1", posted_payload, "approved")
            with patch(
                "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
                return_value=verified,
            ):
                payment = reconcile_payment(payment)
            first_expiry = payment.premium_expires_at
            with patch(
                "Blueprints.services.subscription.mercado_pago_payments_service.get_payment"
            ) as get_payment:
                payment = reconcile_payment(payment)
            get_payment.assert_not_called()
            self.assertEqual(payment.premium_expires_at, first_expiry)
            self.assertEqual((user.plano, user.status_assinatura), ("pro", "active"))
            self.assertEqual(
                payment.premium_expires_at.replace(tzinfo=timezone.utc)
                - payment.approved_at.replace(tzinfo=timezone.utc),
                timedelta(days=30),
            )

    def test_non_credit_methods_are_rejected_server_side(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/api/payment/card", method="POST"):
            user = self.create_user("card@example.com")
            for payment_type in ("debit_card", "prepaid_card", "account_money"):
                with self.subTest(payment_type=payment_type), patch(
                    "Blueprints.services.subscription.mercado_pago_payments_service.mercado_pago_request",
                    return_value=[
                        {"id": "visa", "payment_type_id": payment_type, "status": "active"}
                    ],
                ):
                    with self.assertRaises(CardPaymentValidationError):
                        create_card_payment(
                            user,
                            self.card_request(),
                            "11111111-2222-4333-8444-555555555555",
                        )
            self.assertEqual(Payment.query.count(), 0)

    def test_invalid_installments_are_rejected(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/api/payment/card", method="POST"):
            user = self.create_user("card@example.com")
            for installments in (0, 13, "invalid"):
                with self.subTest(installments=installments), self.assertRaises(
                    CardPaymentValidationError
                ):
                    create_card_payment(
                        user,
                        self.card_request(installments=installments),
                        "11111111-2222-4333-8444-555555555555",
                    )

    def test_raw_card_fields_are_rejected_before_provider_call(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/api/payment/card", method="POST"):
            user = self.create_user("card@example.com")
            payload = self.card_request()
            payload["card_number"] = "4111111111111111"
            with patch(
                "Blueprints.services.subscription.mercado_pago_payments_service.mercado_pago_request"
            ) as provider_request:
                with self.assertRaises(CardPaymentValidationError):
                    create_card_payment(
                        user,
                        payload,
                        "11111111-2222-4333-8444-555555555555",
                    )
            provider_request.assert_not_called()

    def test_card_requires_uuid_idempotency_key(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/api/payment/card", method="POST"):
            user = self.create_user("card@example.com")
            for invalid_key in (None, "", "not-a-uuid"):
                with self.subTest(invalid_key=invalid_key):
                    with self.assertRaises(CardPaymentValidationError):
                        create_card_payment(user, self.card_request(), invalid_key)
            self.assertEqual(Payment.query.count(), 0)

    def test_same_idempotency_key_returns_same_attempt_without_second_charge(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/api/payment/card", method="POST"):
            user = self.create_user("card@example.com")
            post_count = 0

            def provider_request(method, path, **kwargs):
                nonlocal post_count
                if path == "/v1/payment_methods":
                    return [self.credit_method()]
                if path.startswith("/v1/payments/search?"):
                    return {"results": []}
                post_count += 1
                return self.provider_card_data(
                    "pay_idempotent", kwargs["json_payload"], "pending"
                )

            key = "11111111-2222-4333-8444-555555555555"
            with patch(
                "Blueprints.services.subscription.mercado_pago_payments_service.mercado_pago_request",
                side_effect=provider_request,
            ):
                first = create_card_payment(user, self.card_request(), key)
                second = create_card_payment(user, self.card_request(token="different-token"), key)
            self.assertEqual(first, second)
            self.assertEqual(post_count, 1)
            self.assertEqual(Payment.query.count(), 1)

    def test_integrity_error_race_reloads_winning_attempt(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/api/payment/card", method="POST"):
            user = self.create_user("card@example.com")
            key = "11111111-2222-4333-8444-555555555555"
            original_commit = db.session.commit
            winner_attempt_id = key
            first_call = True

            def concurrent_commit():
                nonlocal first_call
                if not first_call:
                    return original_commit()
                first_call = False
                for pending in list(db.session.new):
                    db.session.expunge(pending)
                db.session.add(
                    Payment(
                        user_id=user.id,
                        attempt_id=winner_attempt_id,
                        provider="mercado_pago",
                        external_reference=(
                            f"boost:payment:{winner_attempt_id}:user:{user.id}"
                        ),
                        idempotency_key=key,
                        payment_method="credit_card",
                        status="creating",
                        amount="19.90",
                        currency="BRL",
                    )
                )
                original_commit()
                raise __import__("sqlalchemy").exc.IntegrityError(
                    "INSERT", {}, Exception("concurrent unique winner")
                )

            with patch.object(db.session, "commit", side_effect=concurrent_commit):
                payment = get_or_create_payment_attempt(
                    user,
                    key,
                )
            self.assertEqual(payment.attempt_id, winner_attempt_id)
            self.assertEqual(Payment.query.count(), 1)

    def test_verified_amount_mismatch_never_activates_access(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/api/payment/card", method="POST"):
            user = self.create_user("card@example.com")
            post_payload = {}

            def provider_request(method, path, **kwargs):
                if path == "/v1/payment_methods":
                    return [self.credit_method()]
                if path.startswith("/v1/payments/search?"):
                    return {"results": []}
                if method == "POST":
                    post_payload.update(kwargs["json_payload"])
                    return self.provider_card_data("pay_wrong_amount", post_payload, "approved")
                data = self.provider_card_data("pay_wrong_amount", post_payload, "approved")
                data["transaction_amount"] = "1.00"
                return data

            with patch(
                "Blueprints.services.subscription.mercado_pago_payments_service.mercado_pago_request",
                side_effect=provider_request,
            ):
                create_card_payment(
                    user,
                    self.card_request(),
                    "11111111-2222-4333-8444-555555555555",
                )
            payment = Payment.query.one()
            with patch(
                "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
                side_effect=lambda _payment_id: {
                    **self.provider_card_data(
                        "pay_wrong_amount", post_payload, "approved"
                    ),
                    "transaction_amount": "1.00",
                },
            ):
                with self.assertRaises(MercadoPagoError):
                    reconcile_payment(payment)
            db.session.rollback()
            db.session.refresh(user)
            self.assertEqual((user.plano, user.status_assinatura), ("free", "inactive"))

    def test_reconciliation_throttles_repeated_provider_gets(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/api/payment/card/status"):
            user = self.create_user("card@example.com")
            payment = self.create_pending_attempt(user, provider_payment_id="pay_pending")
            provider_data = self.provider_card_data(
                "pay_pending",
                {
                    "external_reference": payment.external_reference,
                    "transaction_amount": 19.90,
                    "metadata": {
                        "user_id": user.id,
                        "plan": "BOOSTCONVERT_PRO",
                        "attempt_id": payment.attempt_id,
                    },
                },
                "pending",
            )
            with patch(
                "Blueprints.services.subscription.mercado_pago_payments_service.get_payment",
                return_value=provider_data,
            ) as get_payment:
                reconcile_payment(payment)
                reconcile_payment(payment)
            self.assertEqual(get_payment.call_count, 1)
            self.assertEqual((user.plano, user.status_assinatura), ("free", "inactive"))

    def test_reconciliation_recovers_missing_provider_id_by_attempt_reference(self) -> None:
        with self.app.app_context(), self.app.test_request_context("/api/payment/card/status"):
            user = self.create_user("card@example.com")
            payment = self.create_pending_attempt(user, provider_payment_id=None)
            provider_data = self.provider_card_data(
                "pay_reconciled",
                {
                    "external_reference": payment.external_reference,
                    "transaction_amount": 19.90,
                    "metadata": {
                        "user_id": user.id,
                        "plan": "BOOSTCONVERT_PRO",
                        "attempt_id": payment.attempt_id,
                    },
                },
                "approved",
            )
            with patch(
                "Blueprints.services.subscription.mercado_pago_payments_service.mercado_pago_request",
                return_value={"results": [provider_data]},
            ):
                reconciled = reconcile_payment(payment)
            self.assertEqual(reconciled.provider_payment_id, "pay_reconciled")
            self.assertEqual((user.plano, user.status_assinatura), ("pro", "active"))

    def create_user(self, email: str) -> Usuario:
        user = Usuario(email=email, plano="free", status_assinatura="inactive")
        db.session.add(user)
        db.session.commit()
        return user

    def create_pending_attempt(
        self,
        user: Usuario,
        *,
        provider_payment_id: str | None,
    ) -> Payment:
        attempt_id = "11111111-2222-4333-8444-555555555555"
        payment = Payment(
            user_id=user.id,
            attempt_id=attempt_id,
            provider_payment_id=provider_payment_id,
            external_reference=f"boost:payment:{attempt_id}:user:{user.id}",
            plan="BOOSTCONVERT_PRO",
            idempotency_key=attempt_id,
            payment_method="credit_card",
            status="pending",
            amount="19.90",
            currency="BRL",
        )
        db.session.add(payment)
        db.session.commit()
        return payment

    @staticmethod
    def credit_method() -> dict:
        return {"id": "visa", "payment_type_id": "credit_card", "status": "active"}

    @staticmethod
    def card_request(**overrides) -> dict:
        payload = {
            "token": "tok_test_123",
            "payment_method_id": "visa",
            "issuer_id": "123",
            "installments": 1,
            "payer": {
                "email": "card@example.com",
                "identification": {"type": "CPF", "number": "12345678909"},
            },
        }
        payload.update(overrides)
        return payload

    def provider_card_data(
        self,
        payment_id: str,
        request_payload: dict,
        status: str,
    ) -> dict:
        return {
            "id": payment_id,
            "external_reference": request_payload["external_reference"],
            "status": status,
            "payment_method_id": "visa",
            "payment_type_id": "credit_card",
            "transaction_amount": request_payload["transaction_amount"],
            "currency_id": "BRL",
            "collector_id": 123456,
            "live_mode": False,
            "date_created": "2026-07-31T10:15:00Z",
            "date_approved": "2026-07-31T10:16:00Z" if status == "approved" else None,
            "metadata": dict(request_payload["metadata"]),
        }


if __name__ == "__main__":
    unittest.main()
