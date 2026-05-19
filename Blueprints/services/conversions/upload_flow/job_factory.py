import os
import uuid

from flask import current_app
from werkzeug.utils import secure_filename

from models import ConversionJob
from Blueprints.services.conversions.conversion_limits import get_file_size, get_upload_limit_mb, validate_upload_size
from Blueprints.services.conversions.file_security import remove_file_quietly, validate_saved_file, validate_upload_header

def create_single_conversion_job(file, usuario, session_id, allowed_extensions, output_extension, tool_name, options):
    filename = get_secure_filename(file)
    name, extension = split_filename(filename)

    if extension not in allowed_extensions:
        raise ValueError(f"Formato invalido. Permitidos: {', '.join(allowed_extensions)}")

    validate_single_file_upload(file, usuario, extension, output_extension)

    job_id = str(uuid.uuid4())
    job_dir = create_job_directory(job_id)
    input_path = os.path.join(job_dir, filename)
    output_filename = get_output_filename(name, filename, output_extension)
    output_path = os.path.join(job_dir, output_filename)

    save_and_validate_file(file, input_path, extension)

    return build_conversion_job(
        job_id=job_id,
        usuario=usuario,
        session_id=session_id,
        tool_name=tool_name,
        original_filename=filename,
        output_filename=output_filename,
        input_path=input_path,
        output_path=output_path,
        options=options,
    )

def create_pdf_collection_job(files, usuario, session_id, output_extension, tool_name, options):
    validate_pdf_collection_size(files, usuario, output_extension)

    job_id = str(uuid.uuid4())
    job_dir = create_job_directory(job_id)
    saved_filenames = save_pdf_collection_files(files, job_dir)
    output_filename = f"pdf_merge.{output_extension}"
    output_path = os.path.join(job_dir, output_filename)

    return build_conversion_job(
        job_id=job_id,
        usuario=usuario,
        session_id=session_id,
        tool_name=tool_name,
        original_filename=f"{len(saved_filenames)} arquivos PDF",
        output_filename=output_filename,
        input_path=job_dir,
        output_path=output_path,
        options=options,
    )

def get_secure_filename(file):
    if file.filename == "":
        raise ValueError("Arquivo invalido")

    filename = secure_filename(file.filename)

    if not filename:
        raise ValueError("Arquivo invalido")

    return filename

def split_filename(filename):
    name, ext = os.path.splitext(filename)
    extension = ext.lower().lstrip(".")
    return name, extension

def validate_single_file_upload(file, usuario, input_extension, output_extension):
    size_valid, size_message = validate_upload_size(file, usuario, input_extension, output_extension)

    if not size_valid:
        raise ValueError(size_message)

    header_valid, header_message = validate_upload_header(file, input_extension)

    if not header_valid:
        raise ValueError(header_message)

def validate_pdf_collection_size(files, usuario, output_extension):
    limit_mb, category, plan_name = get_upload_limit_mb(usuario, "pdf", output_extension)
    total_size = sum(get_file_size(file) for file in files)

    if total_size > limit_mb * 1024 * 1024:
        raise ValueError(
            f"Arquivos muito grandes para o plano {plan_name}. "
            f"Limite para {category}: {limit_mb} MB."
        )

def create_job_directory(job_id):
    job_dir = os.path.join(current_app.instance_path, "conversions", job_id)
    os.makedirs(job_dir, exist_ok=True)
    return job_dir

def get_output_filename(name, original_filename, output_extension):
    output_filename = f"{name}.{output_extension}"

    if output_filename == original_filename:
        return f"{name}_convertido.{output_extension}"

    return output_filename

def save_and_validate_file(file, input_path, extension):
    file.save(input_path)

    saved_valid, saved_message = validate_saved_file(input_path, extension)

    if not saved_valid:
        remove_file_quietly(input_path)
        raise ValueError(saved_message)

def save_pdf_collection_files(files, job_dir):
    saved_filenames = []

    for index, file in enumerate(files, start=1):
        filename = get_secure_filename(file)
        _name, extension = split_filename(filename)

        if extension != "pdf":
            raise ValueError("Todos os arquivos precisam ser PDF.")

        header_valid, header_message = validate_upload_header(file, extension)

        if not header_valid:
            raise ValueError(header_message)

        input_path = os.path.join(job_dir, f"{index:03d}_{filename}")
        save_and_validate_file(file, input_path, extension)
        saved_filenames.append(filename)

    return saved_filenames

def build_conversion_job(job_id, usuario, session_id, tool_name, original_filename, output_filename, input_path, output_path, options):
    return ConversionJob(
         id=job_id
        ,user_id=usuario.id if usuario is not None else None
        ,session_id=session_id if usuario is None else None
        ,tool_name=tool_name
        ,status="queued"
        ,original_filename=original_filename
        ,output_filename=output_filename
        ,input_path=input_path
        ,output_path=output_path
        ,options=options
    )
