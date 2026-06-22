import os
import tempfile
import zipfile
from flask import current_app
from Blueprints.handlers.conversion_error_pages import render_conversion_error_response
from Blueprints.main.job_access import is_job_downloadable
from Blueprints.services.privacy.download_stream import stream_private_download
from Blueprints.services.privacy.file_retention import expire_conversion_job_files


def send_conversion_file(job):
    app = current_app._get_current_object()
    return stream_private_download(
        job.output_path,
        job.output_filename,
        lambda: expire_conversion_job_files(app, job.id),
    )


def send_conversion_batch_zip(jobs):
    downloadable_jobs = [job for job in jobs if is_job_downloadable(job)]
    if not downloadable_jobs:
        return render_conversion_error_response(ValueError("Nenhum arquivo finalizado para baixar."), 409)
    if len(downloadable_jobs) != len(jobs):
        return render_conversion_error_response(ValueError("Aguarde todas as conversoes finalizarem para baixar o lote."), 409)

    zip_path = create_batch_zip(downloadable_jobs)
    app = current_app._get_current_object()
    job_ids = [job.id for job in downloadable_jobs]

    return stream_private_download(
        zip_path,
        "boost_converter_arquivos.zip",
        lambda: cleanup_batch_download(app, zip_path, job_ids),
    )


def cleanup_batch_download(app, zip_path, job_ids):
    try:
        os.remove(zip_path)
    except OSError:
        pass
    for job_id in job_ids:
        expire_conversion_job_files(app, job_id)


def create_batch_zip(jobs):
    zip_file = tempfile.NamedTemporaryFile(prefix="boost_converter_", suffix=".zip", delete=False)
    zip_path = zip_file.name
    zip_file.close()

    used_filenames = set()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for job in jobs:
            archive.write(job.output_path, arcname=get_unique_zip_filename(job.output_filename, used_filenames))
    return zip_path


def get_unique_zip_filename(filename, used_filenames):
    name, extension = os.path.splitext(filename)
    zip_filename = filename
    counter = 2
    while zip_filename in used_filenames:
        zip_filename = f"{name}_{counter}{extension}"
        counter += 1
    used_filenames.add(zip_filename)
    return zip_filename

