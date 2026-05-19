from flask import current_app

from Blueprints.services.conversions.job_queue import submit_conversion_job

def submit_jobs(job_ids, convert_function, usage):
    usage_id = usage.id if usage is not None else None
    app = current_app._get_current_object()

    for job_id in job_ids:
        submit_conversion_job(app, job_id, convert_function, usage_id)
