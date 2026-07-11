from extensions import db
from models import ConversionAuditLog, ConversionJob, DailyUsage, Payment, Subscription, ToolUsage, Usuario
from Blueprints.services.privacy.file_retention import (
    expire_conversion_job_files,
    get_conversions_root,
    remove_and_anonymize_job_files,
)
from Blueprints.services.privacy.processing_registry import get_processing_activities


def export_user_data(usuario):
    return {
        "usuario": {
            "id": usuario.id,
            "email": usuario.email,
            "nome": usuario.nome,
            "plano": usuario.plano,
            "status_assinatura": usuario.status_assinatura,
            "google_connected": bool(usuario.google_id),
        },
        "daily_usages": [
            {
                "usage_date": usage.usage_date.isoformat(),
                "usage_count": usage.usage_count,
                "window_started_at": usage.window_started_at.isoformat()
                if usage.window_started_at
                else None,
            }
            for usage in DailyUsage.query.filter_by(user_id=usuario.id).all()
        ],
        "tool_usages": [
            {
                "tool_name": usage.tool_name,
                "created_at": usage.created_at.isoformat() if usage.created_at else None,
            }
            for usage in ToolUsage.query.filter_by(user_id=usuario.id).all()
        ],
        "conversion_audit_logs": [
            {
                "tool_name": audit.tool_name,
                "status": audit.status,
                "created_at": audit.created_at.isoformat() if audit.created_at else None,
                "updated_at": audit.updated_at.isoformat() if audit.updated_at else None,
            }
            for audit in ConversionAuditLog.query.filter_by(user_id=usuario.id).all()
        ],
        "subscriptions": [
            {
                "provider": subscription.provider,
                "provider_subscription_id": subscription.provider_subscription_id,
                "provider_payment_id": subscription.provider_payment_id,
                "status": subscription.status,
                "amount": str(subscription.amount) if subscription.amount is not None else None,
                "currency": subscription.currency,
                "started_at": subscription.started_at.isoformat() if subscription.started_at else None,
                "next_payment_at": subscription.next_payment_at.isoformat()
                if subscription.next_payment_at
                else None,
                "canceled_at": subscription.canceled_at.isoformat() if subscription.canceled_at else None,
            }
            for subscription in Subscription.query.filter_by(user_id=usuario.id).all()
        ],
        "payments": [
            {
                "provider": payment.provider,
                "provider_subscription_id": payment.provider_subscription_id,
                "provider_payment_id": payment.provider_payment_id,
                "payment_method": payment.payment_method,
                "status": payment.status,
                "amount": str(payment.amount) if payment.amount is not None else None,
                "currency": payment.currency,
                "premium_expires_at": payment.premium_expires_at.isoformat()
                if payment.premium_expires_at
                else None,
                "approved_at": payment.approved_at.isoformat() if payment.approved_at else None,
            }
            for payment in Payment.query.filter_by(user_id=usuario.id).all()
        ],
        "processing_activities": get_processing_activities(),
    }


def correct_user_data(usuario, email=None, nome=None):
    if email is not None:
        usuario.email = email.strip().lower()
    if nome is not None:
        usuario.nome = nome.strip() or None
    db.session.commit()
    return usuario


def delete_user_data(app, usuario):
    with app.app_context():
        usuario = db.session.get(Usuario, usuario.id)
        if usuario is None:
            return

        conversions_root = get_conversions_root(app)
        for job in ConversionJob.query.filter_by(user_id=usuario.id).all():
            remove_and_anonymize_job_files(job, conversions_root)
            db.session.delete(job)

        ToolUsage.query.filter_by(user_id=usuario.id).delete()
        DailyUsage.query.filter_by(user_id=usuario.id).delete()
        ConversionAuditLog.query.filter_by(user_id=usuario.id).delete()
        Payment.query.filter_by(user_id=usuario.id).delete()
        Subscription.query.filter_by(user_id=usuario.id).delete()
        db.session.delete(usuario)
        db.session.commit()


def revoke_google_consent(usuario):
    usuario.google_id = None
    db.session.commit()
    return usuario


def delete_conversion_job_files(app, job_id):
    expire_conversion_job_files(app, job_id)
