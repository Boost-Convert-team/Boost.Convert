from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import inspect
import os

from dotenv import load_dotenv
from extensions import db
from models import ConversionJob, DailyUsage
from Blueprints.services.conversions.conversion_errors import get_user_friendly_conversion_error
from Blueprints.services.conversions.file_security import remove_job_input_quietly
from Blueprints.services.subscription.access_service import increment_daily_usage

load_dotenv()

def get_conversion_workers():
    try:
        return max(1, int(os.getenv("CONVERSION_WORKERS", "6")))
    except ValueError:
        return 6

executor = ThreadPoolExecutor(max_workers=get_conversion_workers())

def submit_conversion_job(app, job_id, convert_function, usage_id=None):
    executor.submit(process_conversion_job, app, job_id, convert_function, usage_id)

def process_conversion_job(app, job_id, convert_function, usage_id=None):
    with app.app_context():
        job = db.session.get(ConversionJob, job_id)

        if job is None: return

        job.status = "processing"
        job.started_at = datetime.utcnow()
        db.session.commit()

        try:
            convert_with_options(convert_function, job.input_path, job.output_path, job.options or {})

            if not os.path.exists(job.output_path):
                raise RuntimeError("Arquivo final nao foi criado.")

            if os.path.getsize(job.output_path) == 0:
                raise RuntimeError("Arquivo final vazio.")

            remove_job_input_quietly(job.input_path, job.output_path)

            job.status = "done"
            job.finished_at = datetime.utcnow()

            if usage_id is not None:
                usage = db.session.get(DailyUsage, usage_id)
                if usage is not None: increment_daily_usage(usage)

            db.session.commit()

        except Exception as exc:
            app.logger.exception("Erro ao processar job de conversao")
            remove_job_input_quietly(job.input_path, job.output_path)
            job.status = "failed"
            job.error_message = get_user_friendly_conversion_error(exc)
            job.finished_at = datetime.utcnow()
            db.session.commit()

def convert_with_options(convert_function, input_path, output_path, options):
    signature = inspect.signature(convert_function)

    if "options" in signature.parameters:
        return convert_function(input_path, output_path, options=options)

    return convert_function(input_path, output_path)
