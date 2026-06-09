from flask import current_app
from Blueprints.services.convertions_services.job_queue import submit_conversion_job

def submit_jobs(job_ids, convert_function, runtime_options_by_job_id=None):
    app = current_app._get_current_object()
    runtime_options_by_job_id = runtime_options_by_job_id or {}
    for job_id in job_ids:
        submit_conversion_job(app, job_id, convert_function, runtime_options_by_job_id.get(job_id))
