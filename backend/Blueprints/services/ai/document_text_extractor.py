import re
import tempfile
import xml.etree.ElementTree as ElementTree
import zipfile
from pathlib import Path

import fitz
from docx import Document

from Blueprints.services.convertions_services.documents.libreoffice_service import (
    run_libreoffice_conversion,
)


ALLOWED_DOCUMENT_ANALYZER_EXTENSIONS = {"pdf", "docx", "doc", "txt", "rtf", "odt", "md"}
DOCUMENT_ANALYZER_MAX_UPLOAD_BYTES = 12 * 1024 * 1024
DOCUMENT_ANALYZER_MAX_TEXT_CHARS = 180000


def extract_document_text(file_path: Path, extension: str) -> str:
    """Extract normalized text from a supported document.

    Example: extract_document_text(Path("contrato.pdf"), "pdf")
    """
    validate_document_extension(extension)
    validate_document_size(file_path)
    text = dispatch_document_extraction(file_path, extension)
    return validate_extracted_document_text(text)


def validate_document_extension(extension: str) -> None:
    """Reject unsupported analyzer document extensions.

    Example: validate_document_extension("pdf")
    """
    if extension in ALLOWED_DOCUMENT_ANALYZER_EXTENSIONS:
        return
    expected = ", ".join(sorted(ALLOWED_DOCUMENT_ANALYZER_EXTENSIONS))
    raise ValueError(f"Arquivo invalido: extensao {extension!r}; esperado uma de: {expected}.")


def validate_document_size(file_path: Path) -> None:
    """Reject uploads that are too large for temporary AI processing.

    Example: validate_document_size(Path("documento.pdf"))
    """
    size = file_path.stat().st_size
    if size <= DOCUMENT_ANALYZER_MAX_UPLOAD_BYTES:
        return
    raise ValueError(
        f"Documento muito grande: {size} bytes; esperado ate "
        f"{DOCUMENT_ANALYZER_MAX_UPLOAD_BYTES} bytes."
    )


def dispatch_document_extraction(file_path: Path, extension: str) -> str:
    """Route extraction to the parser that matches the file extension.

    Example: dispatch_document_extraction(Path("notas.md"), "md")
    """
    extractors = {
        "pdf": extract_pdf_text,
        "docx": extract_docx_text,
        "doc": extract_doc_text,
        "txt": extract_plain_text,
        "rtf": extract_rtf_text,
        "odt": extract_odt_text,
        "md": extract_plain_text,
    }
    return extractors[extension](file_path)


def validate_extracted_document_text(text: str) -> str:
    """Normalize extracted text and reject empty or excessive content.

    Example: validate_extracted_document_text(" texto ")
    """
    normalized = normalize_document_text(text)
    if not normalized:
        raise ValueError("Texto nao extraido: o documento nao retornou conteudo legivel.")
    if len(normalized) > DOCUMENT_ANALYZER_MAX_TEXT_CHARS:
        raise ValueError(
            f"Documento muito grande: {len(normalized)} caracteres extraidos; "
            f"esperado ate {DOCUMENT_ANALYZER_MAX_TEXT_CHARS}."
        )
    return normalized


def normalize_document_text(text: str) -> str:
    """Collapse noisy whitespace while preserving paragraph breaks.

    Example: normalize_document_text("a\\n\\n\\n b")
    """
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pdf_text(file_path: Path) -> str:
    """Extract sorted text from each PDF page.

    Example: extract_pdf_text(Path("relatorio.pdf"))
    """
    with fitz.open(file_path) as document:
        return "\n\n".join(page.get_text("text", sort=True) for page in document)


def extract_docx_text(file_path: Path) -> str:
    """Extract paragraphs from a DOCX document.

    Example: extract_docx_text(Path("contrato.docx"))
    """
    document = Document(file_path)
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def extract_doc_text(file_path: Path) -> str:
    """Extract DOC text through the LibreOffice owned wrapper.

    Example: extract_doc_text(Path("legado.doc"))
    """
    return extract_libreoffice_text(file_path)


def extract_libreoffice_text(file_path: Path) -> str:
    """Convert legacy Office documents to TXT and read the result.

    Example: extract_libreoffice_text(Path("documento.doc"))
    """
    with tempfile.TemporaryDirectory(prefix="boost_document_text_") as temp_dir:
        output_path = Path(temp_dir) / f"{file_path.stem}.txt"
        run_libreoffice_conversion(file_path, output_path, "txt")
        return extract_plain_text(output_path)


def extract_plain_text(file_path: Path) -> str:
    """Read plain text using common encodings.

    Example: extract_plain_text(Path("notas.txt"))
    """
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Arquivo invalido: {file_path.suffix!r}; esperado texto legivel.")


def extract_rtf_text(file_path: Path) -> str:
    """Extract readable text from a simple RTF document.

    Example: extract_rtf_text(Path("notas.rtf"))
    """
    raw_text = extract_plain_text(file_path)
    raw_text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw_text)
    raw_text = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", raw_text)
    return re.sub(r"[{}]", " ", raw_text)


def extract_odt_text(file_path: Path) -> str:
    """Extract text nodes from an ODT content.xml file.

    Example: extract_odt_text(Path("texto.odt"))
    """
    with zipfile.ZipFile(file_path) as archive:
        content = archive.read("content.xml")
    root = ElementTree.fromstring(content)
    return " ".join(root.itertext())
