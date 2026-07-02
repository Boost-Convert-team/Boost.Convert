import html
import os
import re
import textwrap
from html.parser import HTMLParser
from pathlib import Path
from typing import Union
from urllib.parse import unquote, urlsplit


PathLike = Union[str, os.PathLike[str]]

_CHARSET_RE = re.compile(br"<meta[^>]+charset=[\"']?([A-Za-z0-9._-]+)", re.IGNORECASE)
_IMG_SRC_RE = re.compile(
    r"(<img\b[^>]*?\bsrc\s*=\s*)([\"'])(.*?)(\2)",
    re.IGNORECASE | re.DOTALL,
)
_BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "div",
    "figcaption",
    "figure",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "tr",
    "ul",
}
_SKIP_TAGS = {"head", "script", "style", "svg"}


def read_html_document(input_path: PathLike) -> str:
    data = Path(input_path).read_bytes()
    detected_charset = _detect_html_charset(data)
    encodings = [encoding for encoding in (detected_charset, "utf-8-sig", "utf-8", "cp1252", "latin-1") if encoding]

    for encoding in dict.fromkeys(encodings):
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue

    return data.decode("utf-8", errors="replace")


def convert_html_to_docx(input_path: PathLike, output_path: PathLike) -> None:
    from docx import Document
    from html2docx import html2docx

    content = prepare_html_for_docx(read_html_document(input_path), input_path)
    title = Path(input_path).stem or "documento"

    try:
        converted = html2docx(content, title)
        Path(output_path).write_bytes(converted.getvalue())
    except Exception:
        document = Document()
        for line in extract_plain_text(content).splitlines():
            document.add_paragraph(line.rstrip())
        document.save(output_path)


def convert_html_to_pdf(input_path: PathLike, output_path: PathLike) -> None:
    content = read_html_document(input_path)

    try:
        render_html_pdf_with_playwright(content, input_path, output_path)
    except Exception:
        try:
            render_html_pdf_with_pymupdf_story(content, input_path, output_path)
        except Exception:
            render_text_pdf_fallback(content, output_path)


def prepare_html_for_docx(content: str, input_path: PathLike) -> str:
    return resolve_local_image_sources(content, Path(input_path).resolve().parent)


def resolve_local_image_sources(content: str, base_dir: Path) -> str:
    def replace_src(match: re.Match[str]) -> str:
        prefix, quote, src, suffix_quote = match.groups()
        resolved_src = resolve_local_resource_uri(html.unescape(src), base_dir)
        return f"{prefix}{quote}{html.escape(resolved_src, quote=True)}{suffix_quote}"

    return _IMG_SRC_RE.sub(replace_src, content)


def resolve_local_resource_uri(src: str, base_dir: Path) -> str:
    stripped = src.strip()
    if not stripped or stripped.startswith(("#", "data:")):
        return src

    parsed = urlsplit(stripped)
    if parsed.scheme and not _is_windows_drive_scheme(parsed.scheme):
        return src

    path_part = unquote(parsed.path or stripped)
    if parsed.scheme and _is_windows_drive_scheme(parsed.scheme):
        path_part = f"{parsed.scheme}:{path_part}"

    candidate = Path(path_part)
    if not candidate.is_absolute():
        candidate = base_dir / candidate

    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        return src

    if not resolved.is_file():
        return src

    return resolved.as_uri()


def render_html_pdf_with_playwright(content: str, input_path: PathLike, output_path: PathLike) -> None:
    from playwright.sync_api import sync_playwright

    html_content = build_printable_html(content, Path(input_path).resolve().parent)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=["--no-sandbox"])
        try:
            context = browser.new_context(java_script_enabled=False)
            context.route("http://*/*", lambda route: route.abort())
            context.route("https://*/*", lambda route: route.abort())
            page = context.new_page()
            page.set_content(html_content, wait_until="load", timeout=15000)
            page.emulate_media(media="print")
            page.pdf(
                path=os.fspath(output_path),
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                margin={
                    "top": "16mm",
                    "right": "16mm",
                    "bottom": "16mm",
                    "left": "16mm",
                },
            )
            context.close()
        finally:
            browser.close()


def build_printable_html(content: str, base_dir: Path) -> str:
    base_uri = base_dir.as_uri()
    if not base_uri.endswith("/"):
        base_uri += "/"

    head_injection = (
        f'<base href="{html.escape(base_uri, quote=True)}">'
        "<style>"
        "@page{size:A4;margin:16mm;}"
        "body{font-family:Arial,sans-serif;color:#111;line-height:1.45;}"
        "img,svg,video{max-width:100%;height:auto;}"
        "table{border-collapse:collapse;width:100%;}"
        "th,td{border:1px solid #d0d7de;padding:6px;vertical-align:top;}"
        "pre{white-space:pre-wrap;word-break:break-word;}"
        "code{font-family:Consolas,monospace;}"
        "a{color:#0b57d0;text-decoration:none;}"
        "</style>"
    )

    if re.search(r"<head\b[^>]*>", content, flags=re.IGNORECASE):
        return re.sub(r"(<head\b[^>]*>)", r"\1" + head_injection, content, count=1, flags=re.IGNORECASE)

    if re.search(r"<html\b[^>]*>", content, flags=re.IGNORECASE):
        return re.sub(r"(<html\b[^>]*>)", r"\1<head>" + head_injection + "</head>", content, count=1, flags=re.IGNORECASE)

    return f"<!doctype html><html><head>{head_injection}</head><body>{content}</body></html>"


def render_html_pdf_with_pymupdf_story(content: str, input_path: PathLike, output_path: PathLike) -> None:
    import fitz

    base_dir = Path(input_path).resolve().parent
    archive = fitz.Archive(str(base_dir))
    story = fitz.Story(
        build_printable_html(content, base_dir),
        archive=archive,
    )
    mediabox = fitz.paper_rect("a4")
    content_box = mediabox + (54, 54, -54, -54)

    def rectfn(rect_num: int, filled: fitz.Rect) -> tuple[fitz.Rect, fitz.Rect, None]:
        return mediabox, content_box, None

    document = story.write_with_links(rectfn)
    try:
        document.save(output_path)
    finally:
        document.close()


def render_text_pdf_fallback(content: str, output_path: PathLike) -> None:
    import fitz

    text = extract_plain_text(content).strip() or "Arquivo HTML sem texto visivel."
    document = fitz.open()
    page_width, page_height = fitz.paper_size("a4")
    margin = 54
    font_size = 11
    line_height = 15
    max_line_chars = 96

    page = document.new_page(width=page_width, height=page_height)
    y = margin

    for raw_line in text.splitlines():
        wrapped_lines = textwrap.wrap(raw_line, width=max_line_chars, replace_whitespace=False) or [""]
        for line in wrapped_lines:
            if y > page_height - margin:
                page = document.new_page(width=page_width, height=page_height)
                y = margin
            page.insert_text((margin, y), line, fontsize=font_size, fontname="helv")
            y += line_height
        y += 4

    document.save(output_path)
    document.close()


def extract_plain_text(content: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(content)
    parser.close()
    return parser.get_text()


def _detect_html_charset(data: bytes) -> str | None:
    match = _CHARSET_RE.search(data[:4096])
    if not match:
        return None
    try:
        return match.group(1).decode("ascii", errors="ignore")
    except UnicodeDecodeError:
        return None


def _is_windows_drive_scheme(scheme: str) -> bool:
    return len(scheme) == 1 and scheme.isalpha()


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0
        self.in_pre = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag == "br":
            self._newline()
        elif tag == "li":
            self._newline()
            self.parts.append("- ")
        elif tag in _BLOCK_TAGS:
            self._newline()
        if tag == "pre":
            self.in_pre = True

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag == "pre":
            self.in_pre = False
        if tag in _BLOCK_TAGS:
            self._newline()

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        if self.in_pre:
            self.parts.append(data)
            return

        collapsed = re.sub(r"\s+", " ", data)
        if not collapsed.strip():
            return
        if self.parts and not self.parts[-1].endswith((" ", "\n", "- ")):
            self.parts.append(" ")
        self.parts.append(collapsed.strip())

    def get_text(self) -> str:
        lines = []
        for line in "".join(self.parts).splitlines():
            line = line.rstrip()
            if line or (lines and lines[-1]):
                lines.append(line)
        return "\n".join(lines).strip()

    def _newline(self) -> None:
        if self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")
