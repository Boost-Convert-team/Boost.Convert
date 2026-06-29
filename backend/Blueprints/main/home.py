import os
from xml.sax.saxutils import escape

from flask import Blueprint, Response, abort, jsonify, render_template, request, url_for

from Blueprints.handlers.conversion_error_pages import render_conversion_error_response
from Blueprints.main.account_workspace import get_account_workspace
from Blueprints.main.downloads import send_conversion_batch_zip, send_conversion_file
from Blueprints.main.job_access import get_accessible_job_or_404, get_accessible_jobs_from_ids, is_job_downloadable
from Blueprints.main.tools_registry import TOOLS
from Blueprints.services.convertions_services.conversion_options import get_conversion_options

home_bp = Blueprint("home", __name__)

SINGLE_FILE_UNSUPPORTED_ROUTES = {"/convert/pdf-merge"}


def find_tool_by_slug(slug):
    tool_route = f"/convert/{slug}"
    for category_tools in TOOLS.values():
        for tool in category_tools:
            if tool["route"] == tool_route:
                return tool
    return None


def get_tools_for_extension(extension):
    tools = []
    seen_routes = set()

    for category, category_tools in TOOLS.items():
        for tool in category_tools:
            route = tool.get("route", "")
            if route in seen_routes or not route.startswith("/convert/"):
                continue
            if route in SINGLE_FILE_UNSUPPORTED_ROUTES:
                continue
            if extension not in parse_accept_extensions(tool.get("accept", "")):
                continue

            slug = route.removeprefix("/convert/")
            seen_routes.add(route)
            tools.append(
                {
                    "name": format_conversion_label(tool["name"]),
                    "output": get_conversion_output_label(tool["name"], slug),
                    "category": category,
                    "route": route,
                    "page_url": url_for("home.converter_tool", slug=slug),
                }
            )

    return tools


def parse_accept_extensions(accept):
    extensions = set()
    for value in str(accept).split(","):
        value = value.strip().lower()
        if value.startswith("."):
            extensions.add(value.lstrip("."))
    return extensions


def format_conversion_label(name):
    return name.replace(" -> ", " para ")


def get_conversion_output_label(name, slug):
    if " -> " in name:
        return name.split(" -> ", 1)[1].strip().upper()
    if "-to-" in slug:
        return slug.split("-to-", 1)[1].replace("-", " ").upper()
    return format_conversion_label(name)


@home_bp.route("/")
def home():
    return render_template("home.html")


@home_bp.route("/robots.txt")
def robots_txt():
    content = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            f"Sitemap: {url_for('home.sitemap_xml', _external=True)}",
            "",
        ]
    )
    return Response(content, mimetype="text/plain")


@home_bp.route("/sitemap.xml")
def sitemap_xml():
    urls = [
        url_for("home.home", _external=True),
        url_for("home.tools", _external=True),
        url_for("main.planos", _external=True),
        url_for("home.sobre", _external=True),
        url_for("auth.login", _external=True),
        url_for("auth.registrar", _external=True),
        url_for("youtube_downloads.youtube_download", _external=True),
    ]

    for category_tools in TOOLS.values():
        for tool in category_tools:
            route = str(tool.get("route", ""))
            if route.startswith("/convert/"):
                urls.append(url_for("home.converter_tool", slug=route.removeprefix("/convert/"), _external=True))

    unique_urls = list(dict.fromkeys(urls))
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for page_url in unique_urls:
        sitemap.append(f"    <url><loc>{escape(page_url)}</loc></url>")
    sitemap.append("</urlset>")
    return Response("\n".join(sitemap), mimetype="application/xml")


@home_bp.route("/api/conversion-options")
def conversion_options_for_extension():
    extension = (request.args.get("extension") or "").lower().lstrip(".").strip()
    if not extension:
        return jsonify({"extension": "", "tools": []})

    return jsonify({"extension": extension, "tools": get_tools_for_extension(extension)})


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
    return render_template("tools.html", tools=TOOLS)


@home_bp.route("/tools/<slug>")
def converter_tool(slug):
    tool = find_tool_by_slug(slug)
    if tool is None:
        abort(404)
    return render_template(
        "converter_tool.html",
        tool=tool,
        conversion_options=get_conversion_options(tool["route"]),
    )


@home_bp.route("/conversions/<job_id>")
def conversion_status(job_id):
    job = get_accessible_job_or_404(job_id)
    return render_template(
        "conversion_status.html",
        job=job,
        is_downloadable=is_job_downloadable(job),
    )


@home_bp.route("/conversions/batch/<job_ids>")
def conversion_batch_status(job_ids):
    requested_ids = [job_id for job_id in job_ids.split(",") if job_id]
    jobs = get_accessible_jobs_from_ids(requested_ids)
    downloadable_job_ids = {job.id for job in jobs if is_job_downloadable(job)}
    return render_template(
        "conversion_batch_status.html",
        jobs=jobs,
        has_pending_jobs=any(job.status in ["queued", "processing"] for job in jobs),
        job_ids=",".join(requested_ids),
        all_jobs_downloadable=bool(jobs) and len(downloadable_job_ids) == len(jobs),
        downloadable_job_ids=downloadable_job_ids,
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
            "download_url": f"/conversions/{job.id}/download" if is_job_downloadable(job) else None,
        }
    )


@home_bp.route("/conversions/<job_id>/download")
def conversion_download(job_id):
    job = get_accessible_job_or_404(job_id)
    if job.status != "done":
        return render_conversion_error_response(ValueError("Conversao ainda nao finalizada."), 409)
    if not os.path.exists(job.output_path):
        return render_conversion_error_response(ValueError("Arquivo final nao encontrado."), 404)
    return send_conversion_file(job)


@home_bp.route("/conversions/batch/<job_ids>/download")
def conversion_batch_download(job_ids):
    requested_ids = [job_id for job_id in job_ids.split(",") if job_id]
    jobs = get_accessible_jobs_from_ids(requested_ids)
    return send_conversion_batch_zip(jobs)
