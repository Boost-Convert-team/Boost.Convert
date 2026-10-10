import sys
import tempfile
import unittest
from pathlib import Path

import pymupdf

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.convertions_services.documents.pdf_to_html_service import convert_pdf_html


class PdfToHtmlServiceTests(unittest.TestCase):
    def test_output_is_a_standalone_page_that_keeps_the_pdf_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "relatorio.pdf"
            target = Path(directory) / "relatorio.html"
            document = pymupdf.open()
            document.set_metadata({"title": "Relatório <Q3>"})
            page = document.new_page()
            page.insert_text((72, 80), "Coluna esquerda")
            page.insert_text((330, 80), "Coluna direita")
            document.save(source)
            document.close()

            convert_pdf_html(source, target)
            html = target.read_text(encoding="utf-8")

        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertIn('<meta charset="utf-8">', html)
        self.assertIn("<title>Relatório &lt;Q3&gt;</title>", html)
        # Lines carry top/left from PyMuPDF; the stylesheet must position them.
        self.assertIn("p { position: absolute;", html)
        self.assertIn("left:330.0pt", html)


if __name__ == "__main__":
    unittest.main()
