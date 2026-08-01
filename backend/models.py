from flask_login import UserMixin
from extensions import db
from datetime import datetime, timezone
from uuid import uuid4

def utc_now(): return datetime.now(timezone.utc)

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    senha = db.Column(db.String(255), nullable=True)
    nome = db.Column(db.String(200), nullable=True)
    google_id = db.Column(db.String(255), unique=True, nullable=True)

    plano = db.Column(db.String(20), nullable=False, default="free")
    status_assinatura = db.Column(db.String(20), nullable=False, default="inactive")

class Subscription(db.Model):
    __tablename__ = "subscriptions"
    __table_args__ = (
        db.UniqueConstraint(
            "provider",
            "provider_subscription_id",
            name="uq_subscriptions_provider_subscription_id",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    provider = db.Column(db.String(50), nullable=False, default="mercado_pago", index=True)
    provider_subscription_id = db.Column(db.String(120), nullable=True, index=True)
    provider_payment_id = db.Column(db.String(120), nullable=True, index=True)
    external_reference = db.Column(db.String(255), nullable=True, index=True)
    plan = db.Column(db.String(50), nullable=True, index=True)
    status = db.Column(db.String(50), nullable=False, default="pending", index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=True)
    currency = db.Column(db.String(10), nullable=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    next_payment_at = db.Column(db.DateTime(timezone=True), nullable=True)
    paid_through_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    latest_payment_status = db.Column(db.String(50), nullable=True, index=True)
    canceled_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user = db.relationship("Usuario", backref=db.backref("subscriptions", lazy=True))

class Payment(db.Model):
    __tablename__ = "payments"
    __table_args__ = (
        db.UniqueConstraint(
            "provider",
            "provider_payment_id",
            name="uq_payments_provider_payment_id",
        ),
        db.UniqueConstraint(
            "provider",
            "idempotency_key",
            name="uq_payments_provider_idempotency_key",
        ),
        db.UniqueConstraint(
            "provider",
            "attempt_id",
            name="uq_payments_provider_attempt_id",
        ),
        db.Index(
            "uq_payments_provider_attempt_external_reference",
            "provider",
            "external_reference",
            unique=True,
            postgresql_where=db.text("external_reference LIKE 'boost:payment:%'"),
            sqlite_where=db.text("external_reference LIKE 'boost:payment:%'"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    provider = db.Column(db.String(50), nullable=False, default="mercado_pago", index=True)
    provider_subscription_id = db.Column(db.String(120), nullable=True, index=True)
    provider_payment_id = db.Column(db.String(120), nullable=True, index=True)
    attempt_id = db.Column(db.String(36), nullable=False, default=lambda: str(uuid4()), index=True)
    external_reference = db.Column(db.String(255), nullable=True, index=True)
    plan = db.Column(db.String(50), nullable=True, index=True)
    idempotency_key = db.Column(db.String(64), nullable=True, index=True)
    payment_method = db.Column(db.String(50), nullable=False, index=True)
    provider_payment_method_id = db.Column(db.String(50), nullable=True, index=True)
    payment_type = db.Column(db.String(50), nullable=True, index=True)
    status = db.Column(db.String(50), nullable=False, default="pending", index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=True)
    currency = db.Column(db.String(10), nullable=True)
    premium_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    payment_created_at = db.Column(db.DateTime(timezone=True), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    pix_qr_code = db.Column(db.Text, nullable=True)
    pix_qr_code_base64 = db.Column(db.Text, nullable=True)
    pix_ticket_url = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    last_provider_sync_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)

    user = db.relationship("Usuario", backref=db.backref("payments", lazy=True))

class PaymentWebhookEvent(db.Model):
    __tablename__ = "payment_webhook_events"
    __table_args__ = (
        db.UniqueConstraint(
            "provider",
            "provider_event_id",
            name="uq_payment_webhook_events_provider_event_id",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), nullable=False, default="mercado_pago", index=True)
    provider_event_id = db.Column(db.String(120), nullable=True, index=True)
    event_type = db.Column(db.String(80), nullable=False)
    resource_id = db.Column(db.String(120), nullable=True, index=True)
    status = db.Column(db.String(40), nullable=False, default="processed")
    payload = db.Column(db.JSON, nullable=False, default=dict)
    processed_at = db.Column(db.DateTime(timezone=True), default=utc_now)

class ToolUsage(db.Model):
    __tablename__ = "tool_usages"

    id = db.Column(db.Integer, primary_key=True)

    user = db.relationship("Usuario", backref="tool_usages")
    user_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    session_id = db.Column(db.String(255), nullable=True)

    tool_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)

class DailyUsage(db.Model):
    __tablename__ = "daily_usages"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer,db.ForeignKey("usuarios.id"),nullable=True)

    session_id = db.Column(db.String(255), nullable=True)
    usage_date = db.Column(db.Date, nullable=False)
    window_started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    usage_count = db.Column(db.Integer, nullable=False, default=0)

    user = db.relationship("Usuario",backref=db.backref("daily_usages", lazy=True))

class ConversionJob(db.Model):
    __tablename__ = "conversion_jobs"

    id = db.Column(db.String(36), primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    session_id = db.Column(db.String(255), nullable=True)

    tool_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="queued")

    original_filename = db.Column(db.String(255), nullable=False)
    output_filename = db.Column(db.String(255), nullable=False)
    input_path = db.Column(db.String(500), nullable=False)
    output_path = db.Column(db.String(500), nullable=False)
    options = db.Column(db.JSON, nullable=False, default=dict)
    error_message = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)

    user = db.relationship("Usuario", backref=db.backref("conversion_jobs", lazy=True))

class ConversionAuditLog(db.Model):
    __tablename__ = "conversion_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(36), unique=True, nullable=False, index=True)

    user_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    session_id = db.Column(db.String(255), nullable=True)

    tool_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now)

    user = db.relationship("Usuario", backref=db.backref("conversion_audit_logs", lazy=True))
