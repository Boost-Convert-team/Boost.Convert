from concurrent.futures import ThreadPoolExecutor
import inspect
import os
from dotenv import load_dotenv
from extensions import db
from models import ConversionJob, utc_now
from Blueprints.services.convertions_services.errors.conversion_errors import get_user_friendly_conversion_error
from Blueprints.services.convertions_services.validation.file_security import remove_job_input_quietly

load_dotenv()
def get_conversion_workers():
    try: return max(1, int(os.getenv("CONVERSION_WORKERS", "6")))
    except ValueError: return 6
    
executor = ThreadPoolExecutor(max_workers=get_conversion_workers())

def submit_conversion_job(app, job_id, convert_function): executor.submit(process_conversion_job, app, job_id, convert_function)

def process_conversion_job(app, job_id, convert_function):
    with app.app_context():
        job = db.session.get(ConversionJob, job_id)

        if job is None: return

        job.status = "processing"
        job.started_at = utc_now()
        db.session.commit()
        try:
            convert_with_options(convert_function, job.input_path, job.output_path, job.options or {})

            if not os.path.exists(job.output_path): raise RuntimeError("Arquivo final nao foi criado.")
            if os.path.getsize(job.output_path) == 0: raise RuntimeError("Arquivo final vazio.")

            remove_job_input_quietly(job.input_path, job.output_path)

            job.status = "done"
            job.finished_at = utc_now()
            db.session.commit()

        except Exception as exc:
            app.logger.exception("Erro ao processar job de conversao")
            remove_job_input_quietly(job.input_path, job.output_path)

            job.status = "failed"
            job.error_message = get_user_friendly_conversion_error(exc)
            job.finished_at = utc_now()
            db.session.commit()

def convert_with_options(convert_function, input_path, output_path, options):
    if "options" in inspect.signature(convert_function).parameters: return convert_function(input_path, output_path, options=options)
    return convert_function(input_path, output_path)
