from datetime import datetime, timezone

from flask_login import UserMixin

from extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    senha = db.Column(db.String(255), nullable=True)
    nome = db.Column(db.String(200), nullable=True)
    google_id = db.Column(db.String(255), unique=True, nullable=True)
    plano = db.Column(db.String(20), nullable=False, default="free")


class DailyUsage(db.Model):
    __tablename__ = "daily_usages"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=True, index=True
    )

    session_id = db.Column(db.String(255), nullable=True, index=True)
    usage_date = db.Column(db.Date, nullable=False)
    window_started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    usage_count = db.Column(db.Integer, nullable=False, default=0)

    user = db.relationship("Usuario", backref=db.backref("daily_usages", lazy=True))


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
    __table_args__ = (
        db.UniqueConstraint("job_id"),
        db.Index("ix_conversion_audit_logs_job_id", "job_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(36), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    session_id = db.Column(db.String(255), nullable=True)

    tool_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now)

    user = db.relationship(
        "Usuario", backref=db.backref("conversion_audit_logs", lazy=True)
    )
