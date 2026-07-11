import os
from dataclasses import asdict
from datetime import date
from xml.sax.saxutils import escape

from flask import Blueprint, Response, abort, current_app, jsonify, redirect, render_template, request, url_for

from Blueprints.handlers.conversion_error_pages import render_conversion_error_response
from Blueprints.main.account_workspace import get_account_workspace
from Blueprints.main.downloads import send_conversion_batch_zip, send_conversion_file
from Blueprints.main.guide_content import GUIDE_CONTENT
from Blueprints.main.job_access import get_accessible_job_or_404, get_accessible_jobs_from_ids, is_job_downloadable
from Blueprints.main.seo_catalog import (
    CATEGORIES,
    GUIDES,
    UPDATED_AT,
    as_serializable_dict,
    get_guide_seo,
    get_hub_seo,
    get_page_seo,
    get_tool_seo,
)
from Blueprints.main.seo_helpers import (
    article_schema,
    breadcrumb_schema,
    build_seo,
    faq_schema,
    organization_schema,
    public_url,
    software_application_schema,
    website_schema,
)
from Blueprints.main.tools_registry import TOOLS
from Blueprints.services.convertions_services.conversion_options import get_conversion_options
from Blueprints.services.convertions_services.conversion_rules.conversion_limits import get_tool_limit_info

home_bp = Blueprint("home", __name__)

SINGLE_FILE_UNSUPPORTED_ROUTES = {"/convert/pdf-merge"}
HUB_ICONS = {
    "pdf": "file-text",
    "documents": "files",
    "images": "image",
    "video": "play-circle",
    "audio": "audio-lines",
}
HUB_CARD_CLASSES = {
    "pdf": "tool-card-documentos",
    "documents": "tool-card-documentos",
    "images": "tool-card-imagens",
    "video": "tool-card-videos",
    "audio": "tool-card-audios",
}


def iter_functional_tools():
    """Yield the existing converter registry without changing its records."""
    for source_category, category_tools in TOOLS.items():
        for tool in category_tools:
            route = str(tool.get("route", ""))
            if not route.startswith("/convert/"):
                continue
            yield source_category, route.removeprefix("/convert/"), tool


def get_functional_tool_index():
    return {slug: tool for _, slug, tool in iter_functional_tools()}


def find_tool_by_slug(slug):
    tool_route = f"/convert/{slug}"
    for category_tools in TOOLS.values():
        for tool in category_tools:
            if tool["route"] == tool_route:
                return tool
    return None


def related_tools_for_job(job):
    """Resolve next-step links from presentation metadata only."""
    normalized_name = str(getattr(job, "tool_name", "")).strip().lower()
    slug = next(
        (
            candidate_slug
            for _, candidate_slug, _ in iter_functional_tools()
            if candidate_slug.replace("-", "_") == normalized_name
        ),
        None,
    )
    if not slug:
        return []
    tool = find_tool_by_slug(slug)
    if tool is None:
        return []
    record = get_tool_seo(slug, name=str(tool.get("name", "")), accept=str(tool.get("accept", "")))
    functional_index = get_functional_tool_index()
    return [
        card
        for related_slug in record.related_tools
        for card in [resolve_tool_card(related_slug, functional_index)]
        if card
    ]


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


def breadcrumb_items(*items):
    return [
        {
            "name": label,
            "label": label,
            "url": public_url(path),
        }
        for label, path in items
    ]


def resolve_tool_card(slug, functional_index=None):
    functional_index = functional_index or get_functional_tool_index()
    tool = functional_index.get(slug)
    if tool is None:
        return None
    record = get_tool_seo(slug, name=str(tool.get("name", "")), accept=str(tool.get("accept", "")))
    return {
        "slug": slug,
        "name": format_conversion_label(str(tool.get("name") or record.h1)),
        "title": record.h1,
        "description": record.description,
        "url": public_url(record.path),
        "page_route": record.path,
        "icon": tool.get("icon", HUB_ICONS.get(record.category, "file")),
        "category": record.category,
    }


def resolve_guide_card(slug):
    guide = GUIDES.get(slug)
    if guide is None or guide.status != "indexable":
        return None
    data = as_serializable_dict(guide)
    data.update(
        {
            "meta_description": guide.description,
            "excerpt": guide.summary,
            "read_time": "6 min de leitura",
        }
    )
    return data


def build_tool_page_seo(tool, slug):
    record = get_tool_seo(slug, name=str(tool.get("name", "")), accept=str(tool.get("accept", "")))
    record_data = as_serializable_dict(record)
    functional_index = get_functional_tool_index()
    related_tools = [resolve_tool_card(item, functional_index) for item in record.related_tools]
    category = get_hub_seo(record.category)
    breadcrumbs = breadcrumb_items(
        ("Início", "/"),
        (category.h1, category.path),
        (record.h1, record.path),
    )
    limit_info = get_tool_limit_info(tool)
    real_limits = [
        f"Plano gratuito: arquivos de até {limit_info['free_upload_limit_label']} nesta categoria.",
        f"Plano Pro: arquivos de até {limit_info['pro_upload_limit_label']} nesta categoria.",
        f"Plano gratuito: até {limit_info['free_daily_limit']} conversões a cada 24 horas.",
    ]
    if tool.get("multiple"):
        real_limits.append(
            "Envios múltiplos: até "
            f"{limit_info['free_file_count_limit']} arquivos no Free e "
            f"{limit_info['pro_file_count_limit']} no Pro."
        )

    seo = build_seo(
        title=record.title,
        meta_description=record.description,
        path=record.path,
        robots="index, follow" if record.status == "indexable" else "noindex, follow",
        description=record.description,
        h1=record.h1,
        intro=record.intro,
        how_to=record_data["how_to"],
        benefits=list(record.benefits),
        limitations=[*record.limitations, *real_limits],
        security_text=list(record.security),
        faqs=record_data["faq"],
        related_tools=[item for item in related_tools if item],
        breadcrumbs=breadcrumbs,
        updated_at=record.updated_at.isoformat(),
        status=record.status,
    )
    seo["schemas"] = [
        software_application_schema(seo),
        breadcrumb_schema(breadcrumbs),
        faq_schema(seo["faqs"]),
    ]
    return seo


def build_page_seo(page_key, *, robots=None, schemas=()):
    page = get_page_seo(page_key)
    breadcrumbs = breadcrumb_items(("Início", "/"), (page.h1, page.path))
    page_data = as_serializable_dict(page)
    page_data.update(
        {
            "meta_description": page.description,
            "description": page.description,
            "breadcrumbs": breadcrumbs,
        }
    )
    seo = build_seo(
        title=page.title,
        meta_description=page.description,
        path=page.path,
        robots=robots or page.robots,
        schemas=schemas,
        description=page.description,
        h1=page.h1,
        intro=page.intro,
        breadcrumbs=breadcrumbs,
        updated_at=page.updated_at.isoformat(),
        status=page.status,
    )
    if not schemas and page.path != "/":
        seo["schemas"] = [breadcrumb_schema(breadcrumbs)]
    return page_data, seo


def build_hub_page(hub_key):
    hub = get_hub_seo(hub_key)
    functional_index = get_functional_tool_index()
    cards = []
    for _, slug, tool in iter_functional_tools():
        record = get_tool_seo(slug, name=str(tool.get("name", "")), accept=str(tool.get("accept", "")))
        if record.category == hub_key:
            card = resolve_tool_card(slug, functional_index)
            if card:
                cards.append(card)

    breadcrumbs = breadcrumb_items(("Início", "/"), (hub.h1, hub.path))
    related_hubs = [
        {
            "name": item.name,
            "title": item.h1,
            "description": item.description,
            "url": public_url(item.path),
            "icon": HUB_ICONS[key],
            "card_class": HUB_CARD_CLASSES[key],
        }
        for key, item in CATEGORIES.items()
        if key != hub_key
    ]
    hub_data = as_serializable_dict(hub)
    hub_data.update(
        {
            "meta_description": hub.description,
            "icon": HUB_ICONS[hub_key],
            "card_class": HUB_CARD_CLASSES[hub_key],
            "tools": cards,
            "breadcrumbs": breadcrumbs,
            "related_hubs": related_hubs,
            "tools_description": f"{len(cards)} ferramentas funcionais nesta categoria.",
        }
    )
    seo = build_seo(
        title=hub.title,
        meta_description=hub.description,
        path=hub.path,
        description=hub.description,
        h1=hub.h1,
        intro=hub.intro,
        breadcrumbs=breadcrumbs,
        schemas=[breadcrumb_schema(breadcrumbs)],
    )
    return hub_data, seo


@home_bp.route("/")
def home():
    page, seo = build_page_seo(
        "home",
        schemas=(organization_schema(), website_schema()),
    )
    return render_template("home.html", page=page, seo=seo)


@home_bp.route("/robots.txt")
def robots_txt():
    content = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /api/",
            "Disallow: /checkout/",
            "Disallow: /checkout-pro",
            "Disallow: /checkout-pix",
            "Disallow: /convert/",
            "Disallow: /conversions/",
            "Disallow: /conta",
            "Disallow: /dashboard",
            "Disallow: /login",
            "Disallow: /logout",
            "Disallow: /registrar",
            "Disallow: /cadastro",
            "Disallow: /webhook",
            "Disallow: /webhooks/",
            f"Sitemap: {public_url('/sitemap.xml')}",
            "",
        ]
    )
    response = Response(content, mimetype="text/plain")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@home_bp.route("/sitemap.xml")
def sitemap_xml():
    entries = {
        get_page_seo("home").path: get_page_seo("home").updated_at,
        get_page_seo("tools").path: get_page_seo("tools").updated_at,
        "/planos": UPDATED_AT,
        get_page_seo("about").path: get_page_seo("about").updated_at,
        get_page_seo("security").path: get_page_seo("security").updated_at,
        get_page_seo("privacy").path: get_page_seo("privacy").updated_at,
        get_page_seo("contact").path: get_page_seo("contact").updated_at,
        get_page_seo("terms").path: get_page_seo("terms").updated_at,
        get_page_seo("guides").path: get_page_seo("guides").updated_at,
    }
    for hub in CATEGORIES.values():
        if hub.status == "indexable":
            entries[hub.path] = hub.updated_at
    for _, slug, tool in iter_functional_tools():
        record = get_tool_seo(slug, name=str(tool.get("name", "")), accept=str(tool.get("accept", "")))
        if record.status == "indexable":
            entries[record.path] = record.updated_at
    for guide in GUIDES.values():
        if guide.status == "indexable":
            entries[guide.path] = guide.updated_at

    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, updated_at in entries.items():
        lastmod = updated_at.isoformat() if isinstance(updated_at, date) else str(updated_at)
        sitemap.append(
            "    <url>"
            f"<loc>{escape(public_url(path))}</loc>"
            f"<lastmod>{escape(lastmod)}</lastmod>"
            "</url>"
        )
    sitemap.append("</urlset>")
    response = Response("\n".join(sitemap), mimetype="application/xml")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@home_bp.route("/api/conversion-options")
def conversion_options_for_extension():
    extension = (request.args.get("extension") or "").lower().lstrip(".").strip()
    if not extension:
        return jsonify({"extension": "", "tools": []})

    return jsonify({"extension": extension, "tools": get_tools_for_extension(extension)})


@home_bp.route("/sobre-nos")
def sobre():
    _, seo = build_page_seo("about")
    return render_template("sobre.html", seo=seo)


@home_bp.route("/sobre")
@home_bp.route("/about")
def sobre_legacy():
    return redirect(url_for("home.sobre"), code=301)


@home_bp.route("/security")
def security_page():
    page, seo = build_page_seo("security")
    page["retention_minutes"] = current_app.config.get("CONVERSION_FILE_RETENTION_MINUTES", 15)
    return render_template("security.html", page=page, seo=seo)


@home_bp.route("/privacy")
def privacy_page():
    page, seo = build_page_seo("privacy")
    return render_template("privacy.html", page=page, seo=seo)


@home_bp.route("/contact")
def contact_page():
    page, seo = build_page_seo("contact")
    page["support_email"] = "boostconvertsuporte@gmail.com"
    page["channels"] = [
        {
            "name": "Instagram",
            "description": "Perfil público do BoostConvert no Instagram.",
            "url": "https://www.instagram.com/boost.convert/",
            "icon": "instagram",
            "external": True,
        }
    ]
    return render_template("contact.html", page=page, seo=seo)


@home_bp.route("/terms")
def terms_page():
    page, seo = build_page_seo("terms")
    return render_template("terms.html", page=page, seo=seo)


@home_bp.route("/conta")
@home_bp.route("/dashboard")
def conta():
    return render_template("conta.html", account_workspace=get_account_workspace())


@home_bp.route("/tools")
def tools():
    _, seo = build_page_seo("tools")
    return render_template("tools.html", tools=TOOLS, seo=seo)


def render_category_hub(hub_key):
    hub, seo = build_hub_page(hub_key)
    return render_template("category_hub.html", hub=hub, seo=seo)


@home_bp.route("/pdf-tools")
def pdf_tools():
    return render_category_hub("pdf")


@home_bp.route("/document-tools")
def document_tools():
    return render_category_hub("documents")


@home_bp.route("/image-tools")
def image_tools():
    return render_category_hub("images")


@home_bp.route("/video-tools")
def video_tools():
    return render_category_hub("video")


@home_bp.route("/audio-tools")
def audio_tools():
    return render_category_hub("audio")


@home_bp.route("/guides")
def guides_index():
    page, seo = build_page_seo("guides")
    guides = [card for slug in GUIDES for card in [resolve_guide_card(slug)] if card]
    page["guides"] = guides
    page["featured_guide"] = guides[0] if guides else None
    return render_template(
        "guides_index.html",
        page=page,
        guides=guides,
        featured_guide=page["featured_guide"],
        seo=seo,
    )


@home_bp.route("/guides/<slug>")
def guide_detail(slug):
    guide = GUIDES.get(slug)
    sections = GUIDE_CONTENT.get(slug)
    if guide is None or sections is None or guide.status != "indexable":
        abort(404)

    functional_index = get_functional_tool_index()
    primary_tool = resolve_tool_card(guide.primary_tool, functional_index)
    related_tools = [resolve_tool_card(item, functional_index) for item in guide.related_tools]
    related_guides = [
        resolve_guide_card(item.slug)
        for item in GUIDES.values()
        if item.slug != slug and item.status == "indexable"
    ][:3]
    breadcrumbs = breadcrumb_items(
        ("Início", "/"),
        ("Guias", "/guides"),
        (guide.h1, guide.path),
    )
    guide_data = as_serializable_dict(guide)
    guide_data.update(
        {
            "meta_description": guide.description,
            "description": guide.description,
            "excerpt": guide.summary,
            "sections": sections,
            "breadcrumbs": breadcrumbs,
            "author": "Equipe BoostConvert",
            "read_time": "6 min de leitura",
        }
    )
    seo = build_seo(
        title=guide.title,
        meta_description=guide.description,
        path=guide.path,
        description=guide.description,
        h1=guide.h1,
        intro=guide.summary,
        breadcrumbs=breadcrumbs,
        updated_at=guide.updated_at.isoformat(),
    )
    seo["schemas"] = [
        article_schema(guide_data, seo["canonical_url"]),
        breadcrumb_schema(breadcrumbs),
    ]
    return render_template(
        "guide.html",
        guide=guide_data,
        primary_tool=primary_tool,
        related_tools=[item for item in related_tools if item],
        related_guides=[item for item in related_guides if item],
        breadcrumbs=breadcrumbs,
        seo=seo,
    )


@home_bp.route("/blog")
def blog_index():
    page, seo = build_page_seo("blog", robots="noindex, follow")
    seo["status"] = "noindex"
    return render_template("blog_index.html", page=page, posts=[], seo=seo)


@home_bp.route("/tools/<slug>")
def converter_tool(slug):
    tool = find_tool_by_slug(slug)
    if tool is None:
        abort(404)
    return render_template(
        "converter_tool.html",
        tool=tool,
        conversion_options=get_conversion_options(tool["route"]),
        seo=build_tool_page_seo(tool, slug),
    )


@home_bp.route("/conversions/<job_id>")
def conversion_status(job_id):
    job = get_accessible_job_or_404(job_id)
    return render_template(
        "conversion_status.html",
        job=job,
        is_downloadable=is_job_downloadable(job),
        related_tools=related_tools_for_job(job),
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
        related_tools=related_tools_for_job(jobs[0]) if jobs else [],
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
