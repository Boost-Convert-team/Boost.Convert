from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

from flask import current_app


PUBLIC_ORIGIN = "https://boostconvert.com.br"
SITE_NAME = "BoostConvert"
DEFAULT_DESCRIPTION = (
    "Converta PDF, documentos, imagens, vídeos e áudios online no BoostConvert. "
    "Use ferramentas no navegador, sem instalar programas."
)
PRIVATE_PATH_PREFIXES = (
    "/api/",
    "/cadastro",
    "/checkout",
    "/checkout-pro",
    "/checkout-pix",
    "/conta",
    "/convert/",
    "/conversions/",
    "/dashboard",
    "/login",
    "/logout",
    "/registrar",
    "/webhook",
    "/webhooks/",
)


def get_public_origin() -> str:
    """Return the single production origin used by every SEO signal."""
    configured = str(current_app.config.get("BASE_URL") or PUBLIC_ORIGIN).rstrip("/")
    parsed = urlsplit(configured)
    if parsed.scheme == "https" and parsed.hostname == "boostconvert.com.br":
        return PUBLIC_ORIGIN
    return PUBLIC_ORIGIN


def public_url(path: str = "/") -> str:
    normalized_path = f"/{str(path or '').lstrip('/')}"
    if normalized_path != "/":
        normalized_path = normalized_path.rstrip("/")
    return f"{get_public_origin()}{normalized_path}"


def robots_for_path(path: str) -> str:
    normalized = str(path or "/").rstrip("/") or "/"
    if any(
        normalized == prefix.rstrip("/") or normalized.startswith(f"{prefix.rstrip('/')}/")
        for prefix in PRIVATE_PATH_PREFIXES
    ):
        return "noindex, follow"
    return "index, follow"


def to_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    return {
        name: getattr(value, name)
        for name in dir(value)
        if not name.startswith("_") and not callable(getattr(value, name))
    }


def serialize_date(value: date | datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def build_seo(
    *,
    title: str,
    meta_description: str,
    path: str,
    robots: str = "index, follow",
    schemas: Iterable[dict[str, Any]] = (),
    og_image: str | None = None,
    **content: Any,
) -> dict[str, Any]:
    return {
        "title": title,
        "meta_description": meta_description,
        "canonical_url": public_url(path),
        "robots": robots,
        "og_image": og_image or public_url("/static/img/boost-convert-logo-clean.png"),
        "schemas": list(schemas),
        **content,
    }


def organization_schema() -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "@id": f"{public_url('/')}#organization",
        "name": SITE_NAME,
        "url": public_url("/"),
        "logo": {
            "@type": "ImageObject",
            "url": public_url("/static/img/boost-convert-logo-clean.png"),
        },
        "sameAs": ["https://www.instagram.com/boost.convert/"],
    }


def website_schema() -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "@id": f"{public_url('/')}#website",
        "name": SITE_NAME,
        "url": public_url("/"),
        "inLanguage": "pt-BR",
        "publisher": {"@id": f"{public_url('/')}#organization"},
    }


def software_application_schema(seo: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": seo.get("h1") or seo.get("title") or SITE_NAME,
        "description": seo.get("meta_description") or DEFAULT_DESCRIPTION,
        "url": seo.get("canonical_url") or public_url("/tools"),
        "applicationCategory": "UtilitiesApplication",
        "operatingSystem": "Web",
        "inLanguage": "pt-BR",
        "isAccessibleForFree": True,
        "offers": {
            "@type": "Offer",
            "price": "0",
            "priceCurrency": "BRL",
            "availability": "https://schema.org/InStock",
        },
        "publisher": {"@id": f"{public_url('/')}#organization"},
    }


def breadcrumb_schema(breadcrumbs: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    items = []
    for position, breadcrumb in enumerate(breadcrumbs, start=1):
        item = {
            "@type": "ListItem",
            "position": position,
            "name": breadcrumb.get("name", ""),
        }
        if breadcrumb.get("url"):
            item["item"] = breadcrumb["url"]
        items.append(item)
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": items,
    }


def faq_schema(faqs: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item.get("question", ""),
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": item.get("answer", ""),
                },
            }
            for item in faqs
            if item.get("question") and item.get("answer")
        ],
    }


def article_schema(guide: Mapping[str, Any], canonical_url: str) -> dict[str, Any]:
    updated_at = serialize_date(guide.get("updated_at"))
    published_at = serialize_date(guide.get("published_at") or guide.get("updated_at"))
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": guide.get("h1") or guide.get("title"),
        "description": guide.get("meta_description"),
        "url": canonical_url,
        "mainEntityOfPage": canonical_url,
        "inLanguage": "pt-BR",
        "datePublished": published_at,
        "dateModified": updated_at,
        "author": {"@type": "Organization", "name": SITE_NAME},
        "publisher": {"@id": f"{public_url('/')}#organization"},
    }
