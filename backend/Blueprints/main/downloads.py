import os
import tempfile
import zipfile
from flask import after_this_request, send_file
from Blueprints.main.job_access import is_job_downloadable


def send_conversion_file(job):
    response = send_file(
        job.output_path,
        as_attachment=True,
        download_name=job.output_filename,
        conditional=True,
        etag=True,
        max_age=0,
    )
    add_download_security_headers(response)
    return response


def send_conversion_batch_zip(jobs):
    downloadable_jobs = [job for job in jobs if is_job_downloadable(job)]
    if not downloadable_jobs:
        return "Nenhum arquivo finalizado para baixar.", 409
    if len(downloadable_jobs) != len(jobs):
        return "Aguarde todas as conversoes finalizarem para baixar o lote.", 409

    zip_path = create_batch_zip(downloadable_jobs)

    @after_this_request
    def remove_zip_file(response):
        try:
            os.remove(zip_path)
        except OSError:
            pass
        return response

    response = send_file(
        zip_path,
        as_attachment=True,
        download_name="boost_converter_arquivos.zip",
        conditional=True,
        etag=True,
        max_age=0,
    )
    add_download_security_headers(response)
    return response


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


def add_download_security_headers(response):
    response.headers["Cache-Control"] = "private, max-age=0"
    response.headers["X-Content-Type-Options"] = "nosniff"
