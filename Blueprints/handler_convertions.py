from flask import current_app, redirect, url_for

from extensions import db
from Blueprints.services.conversions.conversion_limits import validate_multi_file_count
from Blueprints.services.conversions.upload_flow.job_factory import create_pdf_collection_job, create_single_conversion_job
from Blueprints.services.conversions.upload_flow.job_submission import submit_jobs
from Blueprints.services.conversions.upload_flow.request_context import get_conversion_request_context, get_uploaded_files

def handle_conversion(allowed_extension, convert_function, output_extension, tool_name):
    try:
        context = get_conversion_request_context()
        files = get_valid_upload_files()
        validate_uploaded_file_count(files, context.usuario)

        jobs = [
            create_single_conversion_job(
                 file=file
                ,usuario=context.usuario
                ,session_id=context.session_id
                ,allowed_extensions=allowed_extension
                ,output_extension=output_extension
                ,tool_name=tool_name
                ,options=context.options
            )
            for file in files
        ]

        job_ids = save_jobs(jobs)
        submit_jobs(job_ids, convert_function, context.usage)

        return redirect_to_job_status(job_ids)

    except PermissionError as exc:
        return str(exc), 403

    except ValueError as exc:
        db.session.rollback()
        current_app.logger.info("Arquivo recusado: %s", exc)
        return str(exc), 400

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Erro ao criar jobs de conversao")
        return "Erro ao processar os arquivos.", 500

def handle_pdf_collection_conversion(convert_function, output_extension, tool_name):
    try:
        context = get_conversion_request_context()
        files = get_valid_upload_files()

        if len(files) < 2:
            return "Envie pelo menos dois arquivos PDF.", 400

        validate_uploaded_file_count(files, context.usuario)

        job = create_pdf_collection_job(
             files=files
            ,usuario=context.usuario
            ,session_id=context.session_id
            ,output_extension=output_extension
            ,tool_name=tool_name
            ,options=context.options
        )

        job_ids = save_jobs([job])
        submit_jobs(job_ids, convert_function, context.usage)

        return redirect(url_for("home.conversion_status", job_id=job.id))

    except PermissionError as exc:
        return str(exc), 403

    except ValueError as exc:
        db.session.rollback()
        current_app.logger.info("Colecao PDF recusada: %s", exc)
        return str(exc), 400

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Erro ao criar job de colecao PDF")
        return "Erro ao processar os arquivos.", 500

def get_valid_upload_files():
    files = get_uploaded_files()

    if not files:
        raise ValueError("Nenhum arquivo enviado")

    return files

def validate_uploaded_file_count(files, usuario):
    count_valid, count_message = validate_multi_file_count(files, usuario)

    if not count_valid:
        raise ValueError(count_message)

def save_jobs(jobs):
    for job in jobs:
        db.session.add(job)

    db.session.commit()
    return [job.id for job in jobs]

def redirect_to_job_status(job_ids):
    if len(job_ids) == 1:
        return redirect(url_for("home.conversion_status", job_id=job_ids[0]))

    return redirect(url_for("home.conversion_batch_status", job_ids=",".join(job_ids)))
