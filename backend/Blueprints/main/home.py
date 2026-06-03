import os
from flask import abort, jsonify, render_template, Blueprint

from Blueprints.main.account_workspace import get_account_workspace
from Blueprints.main.downloads import send_conversion_batch_zip, send_conversion_file
from Blueprints.main.job_access import get_accessible_job_or_404, get_accessible_jobs_from_ids, is_job_downloadable
from Blueprints.main.tools_registry import TOOLS
from Blueprints.services.convertions_services.conversion_limits import get_tool_limit_info, get_tools_with_limit_info
from Blueprints.services.convertions_services.conversion_options import get_conversion_options

home_bp = Blueprint("home", __name__)


def find_tool_by_slug(slug):
    tool_route = f"/convert/{slug}"
    for category_tools in TOOLS.values():
        for tool in category_tools:
            if tool["route"] == tool_route:
                return tool
    return None


@home_bp.route("/")
def home():
    return render_template("home.html")


@home_bp.route("/sobre")
@home_bp.route("/sobre-nos")
def sobre():
    return render_template("sobre.html")


@home_bp.route("/conta")
@home_bp.route("/dashboard")
def conta():
    return render_template("conta.html", account_workspace=get_account_workspace())


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


@home_bp.route("/conversions/<job_id>")
def conversion_status(job_id):
    return render_template("conversion_status.html", job=get_accessible_job_or_404(job_id))


@home_bp.route("/conversions/batch/<job_ids>")
def conversion_batch_status(job_ids):
    requested_ids = [job_id for job_id in job_ids.split(",") if job_id]
    jobs = get_accessible_jobs_from_ids(requested_ids)
    return render_template(
        "conversion_batch_status.html",
        jobs=jobs,
        has_pending_jobs=any(job.status in ["queued", "processing"] for job in jobs),
        job_ids=",".join(requested_ids),
        all_jobs_downloadable=bool(jobs) and all(is_job_downloadable(job) for job in jobs),
    )


@home_bp.route("/conversions/<job_id>/status")
def conversion_status_json(job_id):
    job = get_accessible_job_or_404(job_id)
    return jsonify(
        {
            "id": job.id,
            "status": job.status,
            "tool_name": job.tool_name,
            "original_filename": job.original_filename,
            "output_filename": job.output_filename,
            "options": job.options,
            "error_message": job.error_message,
            "download_url": f"/conversions/{job.id}/download" if job.status == "done" else None,
        }
    )


@home_bp.route("/conversions/<job_id>/download")
def conversion_download(job_id):
    job = get_accessible_job_or_404(job_id)
    if job.status != "done":
        return "Conversao ainda nao finalizada.", 409
    if not os.path.exists(job.output_path):
        return "Arquivo final nao encontrado.", 404
    return send_conversion_file(job)


@home_bp.route("/conversions/batch/<job_ids>/download")
def conversion_batch_download(job_ids):
    requested_ids = [job_id for job_id in job_ids.split(",") if job_id]
    jobs = get_accessible_jobs_from_ids(requested_ids)
    return send_conversion_batch_zip(jobs)
