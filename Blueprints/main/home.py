from flask import abort, after_this_request, jsonify, render_template, send_file, session, Blueprint
from flask_login import current_user
import os
import tempfile
import zipfile

from models import ConversionJob
from Blueprints.main.tools_registry import TOOLS
from Blueprints.services.conversions.conversion_limits import get_tool_limit_info, get_tools_with_limit_info
from Blueprints.services.conversions.conversion_options import get_conversion_options
home_bp = Blueprint('home', __name__)

def find_tool_by_slug(slug):
    tool_route = f"/convert/{slug}"

    for category_tools in TOOLS.values():
        for tool in category_tools:
            if tool["route"] == tool_route:
                return tool

    return None

@home_bp.route('/')
def home():
    return render_template('home.html')

@home_bp.route("/tools")
def tools():
    return render_template("tools.html", tools=get_tools_with_limit_info(TOOLS))

@home_bp.route("/tools/<slug>")
def converter_tool(slug):
    tool = find_tool_by_slug(slug)

    if tool is None:
        abort(404)

    return render_template(
        "converter_tool.html",
        tool=tool,
        tool_limits=get_tool_limit_info(tool),
        conversion_options=get_conversion_options(tool["route"]),
    )

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
    jobs = []

    for job_id in job_ids:
        job = get_accessible_job_or_404(job_id)
        jobs.append(job)

    return jobs

def is_job_downloadable(job):
    return job.status == "done" and os.path.exists(job.output_path)

def get_unique_zip_filename(filename, used_filenames):
    name, extension = os.path.splitext(filename)
    zip_filename = filename
    counter = 2

    while zip_filename in used_filenames:
        zip_filename = f"{name}_{counter}{extension}"
        counter += 1

    used_filenames.add(zip_filename)
    return zip_filename

@home_bp.route("/conversions/<job_id>")
def conversion_status(job_id):
    job = get_accessible_job_or_404(job_id)
    return render_template("conversion_status.html", job=job)

@home_bp.route("/conversions/batch/<job_ids>")
def conversion_batch_status(job_ids):
    requested_ids = [job_id for job_id in job_ids.split(",") if job_id]
    jobs = get_accessible_jobs_from_ids(requested_ids)
    has_pending_jobs = any(job.status in ["queued", "processing"] for job in jobs)
    all_jobs_downloadable = bool(jobs) and all(is_job_downloadable(job) for job in jobs)

    return render_template(
        "conversion_batch_status.html",
        jobs=jobs,
        has_pending_jobs=has_pending_jobs,
        job_ids=",".join(requested_ids),
        all_jobs_downloadable=all_jobs_downloadable,
    )

@home_bp.route("/conversions/<job_id>/status")
def conversion_status_json(job_id):
    job = get_accessible_job_or_404(job_id)

    return jsonify({
        "id": job.id,
        "status": job.status,
        "tool_name": job.tool_name,
        "original_filename": job.original_filename,
        "output_filename": job.output_filename,
        "options": job.options,
        "error_message": job.error_message,
        "download_url": (
            f"/conversions/{job.id}/download"
            if job.status == "done"
            else None
        ),
    })

@home_bp.route("/conversions/<job_id>/download")
def conversion_download(job_id):
    job = get_accessible_job_or_404(job_id)

    if job.status != "done":
        return "Conversao ainda nao finalizada.", 409

    if not os.path.exists(job.output_path):
        return "Arquivo final nao encontrado.", 404

    response = send_file(
        job.output_path,
        as_attachment=True,
        download_name=job.output_filename,
        conditional=True,
        etag=True,
        max_age=0,
    )
    response.headers["Cache-Control"] = "private, max-age=0"
    response.headers["X-Content-Type-Options"] = "nosniff"

    return response

@home_bp.route("/conversions/batch/<job_ids>/download")
def conversion_batch_download(job_ids):
    requested_ids = [job_id for job_id in job_ids.split(",") if job_id]
    jobs = get_accessible_jobs_from_ids(requested_ids)
    downloadable_jobs = [job for job in jobs if is_job_downloadable(job)]

    if not downloadable_jobs:
        return "Nenhum arquivo finalizado para baixar.", 409

    if len(downloadable_jobs) != len(jobs):
        return "Aguarde todas as conversoes finalizarem para baixar o lote.", 409

    zip_file = tempfile.NamedTemporaryFile(prefix="boost_converter_", suffix=".zip", delete=False)
    zip_path = zip_file.name
    zip_file.close()

    used_filenames = set()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for job in downloadable_jobs:
            zip_filename = get_unique_zip_filename(job.output_filename, used_filenames)
            archive.write(job.output_path, arcname=zip_filename)

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
    response.headers["Cache-Control"] = "private, max-age=0"
    response.headers["X-Content-Type-Options"] = "nosniff"

    return response

