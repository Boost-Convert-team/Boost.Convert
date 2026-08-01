import html
import json
import re
import sys
import unittest
import xml.etree.ElementTree as ElementTree
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from Blueprints.main.seo_catalog import GUIDES, TOOL_SEO
from config import Config
from extensions import db


PUBLIC_ORIGIN = "https://boostconvert.com.br"
PRIORITY_TOOL_SLUGS = (
    "pdf-to-docx",
    "docx-to-pdf",
    "pdf-compress",
    "pdf-merge",
    "pdf-split",
    "pdf-to-jpg",
    "jpg-to-png",
    "png-to-jpg",
    "jpg-to-webp",
    "webp-to-jpg",
    "heic-to-jpg",
    "mp4-to-mp3",
    "wav-to-mp3",
)
HUB_PATHS = (
    "/pdf-tools",
    "/image-tools",
    "/video-tools",
    "/audio-tools",
    "/document-tools",
)
GUIDE_SLUGS = (
    "como-converter-pdf-para-word",
    "como-reduzir-pdf",
    "como-transformar-jpg-em-pdf",
    "jpg-vs-png-vs-webp",
    "como-converter-mp4-para-mp3",
    "como-abrir-heic",
)
PRIVATE_PATH_PREFIXES = (
    "/api/",
    "/cadastro",
    "/checkout",
    "/checkout-pro",
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
SITEMAP_NAMESPACE = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
RELATED_SECTION_RE = re.compile(
    r"<section\b(?=[^>]*\baria-labelledby=(?:\"|')"
    r"(?:related-tools-title|related-guides-title)(?:\"|'))[^>]*>"
    r"(.*?)</section>",
    re.IGNORECASE | re.DOTALL,
)
HREF_RE = re.compile(r"<a\b[^>]*\bhref=(?:\"([^\"]+)\"|'([^']+)')", re.IGNORECASE)


class SeoHtmlParser(HTMLParser):
    """Collect head signals and JSON-LD without adding a test dependency."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.canonicals: list[str] = []
        self.meta: dict[str, str] = {}
        self.title_parts: list[str] = []
        self.json_ld: list[dict | list] = []
        self._in_title = False
        self._in_h1 = False
        self.h1_parts: list[list[str]] = []
        self._in_json_ld = False
        self._json_ld_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name.lower(): value or "" for name, value in attrs}
        if tag.lower() == "link":
            rel_tokens = attributes.get("rel", "").lower().split()
            if "canonical" in rel_tokens and attributes.get("href"):
                self.canonicals.append(attributes["href"])
        elif tag.lower() == "meta":
            key = (attributes.get("name") or attributes.get("property") or "").lower()
            if key:
                self.meta[key] = attributes.get("content", "")
        elif tag.lower() == "title":
            self._in_title = True
        elif tag.lower() == "h1":
            self._in_h1 = True
            self.h1_parts.append([])
        elif tag.lower() == "script" and attributes.get("type", "").lower() == "application/ld+json":
            self._in_json_ld = True
            self._json_ld_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._in_h1 and self.h1_parts:
            self.h1_parts[-1].append(data)
        if self._in_json_ld:
            self._json_ld_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False
        elif tag.lower() == "h1":
            self._in_h1 = False
        elif tag.lower() == "script" and self._in_json_ld:
            payload = "".join(self._json_ld_parts).strip()
            if payload:
                self.json_ld.append(json.loads(payload))
            self._in_json_ld = False
            self._json_ld_parts = []

    @property
    def title(self) -> str:
        return " ".join("".join(self.title_parts).split())

    @property
    def h1(self) -> list[str]:
        return [" ".join("".join(parts).split()) for parts in self.h1_parts]


def parse_html(document: str) -> SeoHtmlParser:
    parser = SeoHtmlParser()
    parser.feed(document)
    parser.close()
    return parser


def schema_nodes(payloads: list[dict | list]) -> list[dict]:
    """Flatten top-level arrays and @graph documents into schema nodes."""
    nodes: list[dict] = []
    pending: list[object] = list(payloads)
    while pending:
        value = pending.pop(0)
        if isinstance(value, list):
            pending[0:0] = value
        elif isinstance(value, dict):
            graph = value.get("@graph")
            if isinstance(graph, list):
                pending[0:0] = graph
            else:
                nodes.append(value)
    return nodes


def schema_types(nodes: list[dict]) -> set[str]:
    found: set[str] = set()
    for node in nodes:
        value = node.get("@type")
        if isinstance(value, str):
            found.add(value)
        elif isinstance(value, list):
            found.update(item for item in value if isinstance(item, str))
    return found


def is_private_path(path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    return any(
        normalized == prefix.rstrip("/") or normalized.startswith(f"{prefix.rstrip('/')}/")
        for prefix in PRIVATE_PATH_PREFIXES
    )


class SeoContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Config may already have been evaluated by unittest discovery.  Patch
        # the factory input only while this app is created, then restore it so
        # this module neither reads an external DB nor changes sibling suites.
        overrides = {
            "APP_ENV": "testing",
            "BASE_URL": PUBLIC_ORIGIN,
            "FORCE_HTTPS": False,
            "SESSION_COOKIE_SECURE": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_ENGINE_OPTIONS": {},
        }
        original_config = {name: getattr(Config, name) for name in overrides}
        try:
            for name, value in overrides.items():
                setattr(Config, name, value)
            cls.app = create_app()
        finally:
            for name, value in original_config.items():
                setattr(Config, name, value)
        cls.app.config.update(
            TESTING=True,
            CSRF_ENABLED=False,
            RATE_LIMIT_ENABLED=False,
            CONVERSION_CLEANUP_INTERVAL_MINUTES=60 * 24,
        )
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            db.create_all()

    @classmethod
    def tearDownClass(cls) -> None:
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()

    def assert_indexable_page(self, path: str):
        response = self.client.get(path)
        self.assertEqual(200, response.status_code, path)
        parsed = parse_html(response.get_data(as_text=True))
        expected_canonical = f"{PUBLIC_ORIGIN}{path}"
        self.assertEqual([expected_canonical], parsed.canonicals, path)
        self.assertEqual("index, follow", parsed.meta.get("robots", "").lower(), path)
        self.assertTrue(parsed.title, f"{path} must have a non-empty <title>")
        self.assertTrue(parsed.meta.get("description"), f"{path} must have a meta description")
        self.assertNotIn("http://boostconvert.com.br", response.get_data(as_text=True), path)
        self.assertNotIn("www.boostconvert.com.br", response.get_data(as_text=True), path)
        return response, parsed

    def sitemap_entries(self) -> dict[str, str]:
        response = self.client.get("/sitemap.xml")
        self.assertEqual(200, response.status_code)
        root = ElementTree.fromstring(response.get_data())
        entries: dict[str, str] = {}
        for url_node in root.findall("sm:url", SITEMAP_NAMESPACE):
            location_node = url_node.find("sm:loc", SITEMAP_NAMESPACE)
            last_modified_node = url_node.find("sm:lastmod", SITEMAP_NAMESPACE)
            self.assertIsNotNone(location_node, "every sitemap URL needs a <loc>")
            self.assertIsNotNone(last_modified_node, "every sitemap URL needs a <lastmod>")
            location = (location_node.text or "").strip()
            last_modified = (last_modified_node.text or "").strip()
            self.assertNotIn(location, entries, f"duplicate sitemap URL: {location}")
            entries[location] = last_modified
        self.assertTrue(entries, "sitemap must contain public URLs")
        return entries

    def test_home_canonical_and_global_schemas(self) -> None:
        response, parsed = self.assert_indexable_page("/")
        types = schema_types(schema_nodes(parsed.json_ld))

        self.assertIn("Organization", types)
        self.assertIn("WebSite", types)
        self.assertEqual(["Converta arquivos online."], parsed.h1)
        self.assertNotIn("Converta arquivos em online", response.get_data(as_text=True))

    def test_canonical_is_independent_from_request_host_and_scheme(self) -> None:
        response = self.client.get(
            "/tools/pdf-to-docx",
            base_url="http://www.boostconvert.com.br",
            headers={"X-Forwarded-Host": "untrusted.example", "X-Forwarded-Proto": "http"},
        )
        self.assertEqual(200, response.status_code)
        parsed = parse_html(response.get_data(as_text=True))

        self.assertEqual(
            [f"{PUBLIC_ORIGIN}/tools/pdf-to-docx"],
            parsed.canonicals,
        )

        original_force_https = self.app.config.get("FORCE_HTTPS")
        self.app.config["FORCE_HTTPS"] = True
        try:
            for base_url in ("http://boostconvert.com.br", "https://www.boostconvert.com.br"):
                with self.subTest(base_url=base_url):
                    redirected = self.client.get("/tools/pdf-to-docx?source=test", base_url=base_url)
                    self.assertEqual(301, redirected.status_code)
                    self.assertEqual(
                        f"{PUBLIC_ORIGIN}/tools/pdf-to-docx?source=test",
                        redirected.headers["Location"],
                    )
        finally:
            self.app.config["FORCE_HTTPS"] = original_force_https

    def test_sitemap_contains_only_apex_https_public_urls_with_lastmod(self) -> None:
        entries = self.sitemap_entries()

        for location, last_modified in entries.items():
            parsed = urlsplit(location)
            with self.subTest(location=location):
                self.assertEqual("https", parsed.scheme)
                self.assertEqual("boostconvert.com.br", parsed.hostname)
                self.assertIsNone(parsed.port)
                self.assertFalse(parsed.query)
                self.assertFalse(parsed.fragment)
                self.assertFalse(is_private_path(parsed.path), location)
                date.fromisoformat(last_modified)

        expected_paths = {"/", "/tools", "/guides", *HUB_PATHS}
        expected_paths.update(f"/tools/{slug}" for slug in PRIORITY_TOOL_SLUGS)
        expected_paths.update(f"/guides/{slug}" for slug in GUIDE_SLUGS)
        sitemap_paths = {urlsplit(location).path for location in entries}
        self.assertTrue(expected_paths.issubset(sitemap_paths), expected_paths - sitemap_paths)

    def test_robots_allows_noindex_responses_to_be_crawled_and_declares_sitemap(self) -> None:
        response = self.client.get("/robots.txt")
        body = response.get_data(as_text=True)

        self.assertEqual(200, response.status_code)
        self.assertEqual("text/plain", response.mimetype)
        self.assertIn("User-agent: *", body)
        self.assertIn("Allow: /", body)
        self.assertNotIn("Disallow:", body)
        self.assertIn(f"Sitemap: {PUBLIC_ORIGIN}/sitemap.xml", body)
        self.assertNotIn("http://boostconvert.com.br", body)
        self.assertNotIn("www.boostconvert.com.br", body)

    def test_private_and_error_responses_send_x_robots_tag(self) -> None:
        private_paths = (
            "/login",
            "/dashboard",
            "/checkout-pro",
            "/api/conversion-options?extension=pdf",
        )
        for path in private_paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertLess(response.status_code, 500, path)
                self.assertIn("noindex", response.headers.get("X-Robots-Tag", "").lower())

        missing = self.client.get("/pagina-seo-inexistente")
        self.assertEqual(404, missing.status_code)
        self.assertIn("noindex", missing.headers.get("X-Robots-Tag", "").lower())

    def test_priority_tool_pages_have_canonical_metadata_and_required_schemas(self) -> None:
        titles: set[str] = set()
        for slug in PRIORITY_TOOL_SLUGS:
            path = f"/tools/{slug}"
            with self.subTest(path=path):
                _response, parsed = self.assert_indexable_page(path)
                nodes = schema_nodes(parsed.json_ld)
                types = schema_types(nodes)
                self.assertTrue(
                    {"SoftwareApplication", "BreadcrumbList", "FAQPage"}.issubset(types),
                    f"{path}: missing schemas "
                    f"{{'SoftwareApplication', 'BreadcrumbList', 'FAQPage'}} - {types}",
                )

                application = next(node for node in nodes if node.get("@type") == "SoftwareApplication")
                self.assertEqual(f"{PUBLIC_ORIGIN}{path}", application.get("url"))
                self.assertEqual("Web", application.get("operatingSystem"))
                self.assertTrue(application.get("isAccessibleForFree"))

                faq_page = next(node for node in nodes if node.get("@type") == "FAQPage")
                self.assertTrue(faq_page.get("mainEntity"), f"{path}: empty FAQ schema")

                document = _response.get_data(as_text=True)
                self.assertNotIn("Informações técnicas", document)

                breadcrumb = next(node for node in nodes if node.get("@type") == "BreadcrumbList")
                self.assertGreaterEqual(len(breadcrumb.get("itemListElement", [])), 3)
                self.assertNotIn(parsed.title, titles, f"duplicate title: {parsed.title}")
                titles.add(parsed.title)

    def test_category_hubs_are_indexable_linked_and_have_breadcrumb_schema(self) -> None:
        sitemap_paths = {urlsplit(url).path for url in self.sitemap_entries()}
        for path in HUB_PATHS:
            with self.subTest(path=path):
                response, parsed = self.assert_indexable_page(path)
                self.assertIn(path, sitemap_paths)
                self.assertIn("BreadcrumbList", schema_types(schema_nodes(parsed.json_ld)))
                self.assertRegex(response.get_data(as_text=True), r'href=["\']/tools/[^"\']+')

    def test_guides_are_indexable_and_publish_article_schema(self) -> None:
        self.assert_indexable_page("/guides")
        sitemap_paths = {urlsplit(url).path for url in self.sitemap_entries()}
        for slug in GUIDE_SLUGS:
            path = f"/guides/{slug}"
            with self.subTest(path=path):
                response, parsed = self.assert_indexable_page(path)
                self.assertIn(path, sitemap_paths)
                types = schema_types(schema_nodes(parsed.json_ld))
                self.assertTrue({"Article", "BreadcrumbList"}.issubset(types), types)
                breadcrumb = re.search(
                    r'<nav class="tools-quick-nav breadcrumbs".*?</nav>',
                    response.get_data(as_text=True),
                    re.DOTALL,
                )
                self.assertIsNotNone(breadcrumb)
                self.assertNotIn(GUIDES[slug].h1, breadcrumb.group(0))

    def test_related_tool_and_guide_links_do_not_return_404(self) -> None:
        related_paths: set[str] = set()
        for slug in PRIORITY_TOOL_SLUGS:
            path = f"/tools/{slug}"
            response = self.client.get(path)
            self.assertEqual(200, response.status_code, path)
            document = response.get_data(as_text=True)
            page_links: set[str] = set()
            for section in RELATED_SECTION_RE.findall(document):
                for double_quoted, single_quoted in HREF_RE.findall(section):
                    href = html.unescape(double_quoted or single_quoted).strip()
                    parsed = urlsplit(href)
                    if parsed.hostname and parsed.hostname != "boostconvert.com.br":
                        continue
                    if parsed.path.startswith(("/tools/", "/guides/")):
                        page_links.add(parsed.path)
            self.assertTrue(page_links, f"{path} must expose related tools or guides")
            if TOOL_SEO[slug].related_guides:
                self.assertTrue(
                    any(link.startswith("/guides/") for link in page_links),
                    f"{path} must link to a related guide",
                )
            related_paths.update(page_links)

        for path in sorted(related_paths):
            with self.subTest(related_path=path):
                response = self.client.get(path)
                self.assertEqual(200, response.status_code, f"broken related link: {path}")

    def test_every_sitemap_page_has_unique_metadata_canonical_brand_and_one_h1(self) -> None:
        titles: dict[str, str] = {}
        descriptions: dict[str, str] = {}

        for location in self.sitemap_entries():
            path = urlsplit(location).path
            with self.subTest(path=path):
                _response, parsed = self.assert_indexable_page(path)
                self.assertEqual(1, len(parsed.h1), f"{path} must expose exactly one H1")
                self.assertNotIn("Boost.Convert", parsed.title)
                self.assertNotIn("Boost.Convert", parsed.meta["description"])
                self.assertNotIn(parsed.title, titles, f"duplicate title with {titles.get(parsed.title)}")
                self.assertNotIn(
                    parsed.meta["description"],
                    descriptions,
                    f"duplicate description with {descriptions.get(parsed.meta['description'])}",
                )
                titles[parsed.title] = path
                descriptions[parsed.meta["description"]] = path


if __name__ == "__main__":
    unittest.main()
