from flask import current_app, redirect, url_for
from extensions import db
from Blueprints.services.convertions_services.conversion_limits import validate_multi_file_count
from Blueprints.services.convertions_services.upload_flow.job_factory import create_file_collection_job, create_pdf_collection_job, create_single_conversion_job
from Blueprints.services.convertions_services.upload_flow.job_submission import submit_jobs
from Blueprints.services.convertions_services.upload_flow.request_context import get_conversion_request_context, get_uploaded_files
from Blueprints.services.privacy.audit import create_conversion_audit
from Blueprints.services.subscription.access_service import reserve_tool_usage

def handle_conversion(allowed_extension, convert_function, output_extension, tool_name):
    try:
        context = get_conversion_request_context()
        files = get_valid_upload_files()
        validate_uploaded_file_count(files, context.usuario)
        reserve_usage(context, amount=len(files))
        
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
        return save_submit_and_redirect(jobs, convert_function)
    except Exception as exc:
        return handle_conversion_error(exc, "Arquivo recusado: %s", "Erro ao criar jobs de conversao")


def handle_pdf_collection_conversion(convert_function, output_extension, tool_name):
    try:
        context = get_conversion_request_context()
        files = get_valid_upload_files()

        if len(files) < 2: return "Envie pelo menos dois arquivos PDF.", 400

        validate_uploaded_file_count(files, context.usuario)
        reserve_usage(context, amount=1)

        job = create_pdf_collection_job(
             files=files
            ,usuario=context.usuario
            ,session_id=context.session_id
            ,output_extension=output_extension
            ,tool_name=tool_name
            ,options=context.options
        )
        save_and_submit_jobs([job], convert_function)
        return redirect(url_for("home.conversion_status", job_id=job.id))
    
    except Exception as exc:
        return handle_conversion_error(exc, "Colecao PDF recusada: %s", "Erro ao criar job de colecao PDF")


def handle_file_collection_conversion(allowed_extensions, convert_function, output_extension, tool_name, output_filename, original_label=None):
    try:
        context = get_conversion_request_context()
        files = get_valid_upload_files()

        if len(files) < 1: return "Envie pelo menos um arquivo.", 400

        validate_uploaded_file_count(files, context.usuario)
        reserve_usage(context, amount=1)

        job = create_file_collection_job(
             files=files
            ,usuario=context.usuario
            ,session_id=context.session_id
            ,allowed_extensions=allowed_extensions
            ,output_extension=output_extension
            ,tool_name=tool_name
            ,output_filename=output_filename
            ,original_label=original_label
            ,options=context.options
        )
        save_and_submit_jobs([job], convert_function)
        return redirect(url_for("home.conversion_status", job_id=job.id))
    
    except Exception as exc:
        return handle_conversion_error(exc, "Colecao de arquivos recusada: %s", "Erro ao criar job de colecao de arquivos")

def get_valid_upload_files():
    files = get_uploaded_files()

    if not files: raise ValueError("Nenhum arquivo enviado")
    return files

def validate_uploaded_file_count(files, usuario):
    count_valid, count_message = validate_multi_file_count(files, usuario)

    if not count_valid: raise ValueError(count_message)

def reserve_usage(context, amount): reserve_tool_usage(usuario=context.usuario, session_id=context.session_id, amount=amount)

def save_submit_and_redirect(jobs, convert_function):
    job_ids = save_and_submit_jobs(jobs, convert_function)
    return redirect_to_job_status(job_ids)

def save_and_submit_jobs(jobs, convert_function):
    runtime_options_by_job_id = {job.id: getattr(job, "runtime_options", job.options or {}) for job in jobs}
    job_ids = save_jobs(jobs)
    submit_jobs(job_ids, convert_function, runtime_options_by_job_id)
    return job_ids

def save_jobs(jobs):
    for job in jobs:
        db.session.add(job)
        create_conversion_audit(job)

    db.session.commit()
    return [job.id for job in jobs]

def redirect_to_job_status(job_ids):
    if len(job_ids) == 1: return redirect(url_for("home.conversion_status", job_id=job_ids[0]))
    return redirect(url_for("home.conversion_batch_status", job_ids=",".join(job_ids)))

def handle_conversion_error(exc, refused_log_message, internal_log_message):
    if isinstance(exc, PermissionError): return str(exc), 403
    db.session.rollback()

    if isinstance(exc, ValueError):
        current_app.logger.info(refused_log_message, type(exc).__name__)
        return str(exc), 400
    
    current_app.logger.error("%s: %s", internal_log_message, type(exc).__name__, exc_info=False)
    return "Erro ao processar os arquivos.", 500
