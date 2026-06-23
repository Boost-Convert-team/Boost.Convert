from flask import abort, session
from flask_login import current_user

from models import ConversionJob


def can_access_job(job):
    if current_user.is_authenticated:
        return job.user_id == current_user.id
    return job.session_id == session.get("anon_id")


def get_accessible_job_or_404(job_id):
    job = ConversionJob.query.get_or_404(job_id)
    if not can_access_job(job):
        abort(404)
    return job


def get_accessible_jobs_from_ids(job_ids):
    return [get_accessible_job_or_404(job_id) for job_id in job_ids]


def is_job_downloadable(job):
    import os
    from flask import current_app
    from Blueprints.services.privacy.file_retention import get_conversions_root, is_inside_root

    if job.status != "done" or not os.path.exists(job.output_path):
        return False
    root = get_conversions_root(current_app._get_current_object())
    return is_inside_root(job.output_path, root)
