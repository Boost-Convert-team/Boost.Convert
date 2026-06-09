from extensions import db
from models import ConversionAuditLog, utc_now


def create_conversion_audit(job):
    db.session.add(
        ConversionAuditLog(
            job_id=job.id,
            user_id=job.user_id,
            session_id=job.session_id,
            tool_name=job.tool_name,
            status=job.status,
        )
    )


def update_conversion_audit_status(job, status):
    audit = ConversionAuditLog.query.filter_by(job_id=job.id).first()

    if audit is None:
        audit = ConversionAuditLog(
            job_id=job.id,
            user_id=job.user_id,
            session_id=job.session_id,
            tool_name=job.tool_name,
            status=status,
        )
        db.session.add(audit)

    audit.status = status
    audit.updated_at = utc_now()
