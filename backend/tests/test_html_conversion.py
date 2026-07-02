import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz
from docx import Document


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.convertions_services.documents import html_conversion
from Blueprints.services.convertions_services.documents.html_to_docx_service import (
    convert_html_docx,
)
from Blueprints.services.convertions_services.documents.html_to_pdf_service import (
    convert_html_pdf,
)


class HtmlConversionTests(unittest.TestCase):
    def test_html_to_docx_converts_without_office_processor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "pagina.html"
            output_path = Path(temp_dir) / "pagina.docx"
            input_path.write_text(
                "<h1>Boost HTML</h1><p>Texto convertido sem LibreOffice.</p>",
                encoding="utf-8",
            )

            convert_html_docx(input_path, output_path)

            document = Document(output_path)
            text = "\n".join(paragraph.text for paragraph in document.paragraphs)

        self.assertIn("Boost HTML", text)
        self.assertIn("Texto convertido sem LibreOffice.", text)

    def test_html_to_pdf_fallback_converts_without_browser_or_office_processor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "pagina.html"
            output_path = Path(temp_dir) / "pagina.pdf"
            input_path.write_text(
                "<h1>Boost HTML</h1><p>PDF gerado por fallback Python.</p>",
                encoding="utf-8",
            )

            with patch.object(
                html_conversion,
                "render_html_pdf_with_playwright",
                side_effect=RuntimeError("browser unavailable"),
            ):
                convert_html_pdf(input_path, output_path)

            with fitz.open(output_path) as document:
                text = "\n".join(page.get_text() for page in document)

        self.assertIn("Boost HTML", text)
        self.assertIn("PDF gerado por fallback Python.", text)


if __name__ == "__main__":
    unittest.main()
