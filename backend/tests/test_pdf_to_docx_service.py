import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import fitz


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.convertions_services.documents import pdf_to_docx_service


class PdfToDocxServiceTests(unittest.TestCase):
    def test_multi_page_pdf_uses_parallel_workers(self) -> None:
        with (
            patch.object(pdf_to_docx_service, "get_system_cpu_count", return_value=8),
            patch.dict(
                os.environ,
                {
                    pdf_to_docx_service.DISABLE_PARALLEL_ENV: "0",
                    pdf_to_docx_service.MAX_WORKERS_ENV: "4",
                },
                clear=False,
            ),
        ):
            settings = pdf_to_docx_service.build_pdf_to_docx_settings(page_count=20)

        self.assertEqual(settings, {"multi_processing": True, "cpu_count": 4})

    def test_single_page_pdf_stays_sequential(self) -> None:
        with (
            patch.object(pdf_to_docx_service, "get_system_cpu_count", return_value=8),
            patch.dict(
                os.environ,
                {
                    pdf_to_docx_service.DISABLE_PARALLEL_ENV: "0",
                    pdf_to_docx_service.MAX_WORKERS_ENV: "4",
                },
                clear=False,
            ),
        ):
            settings = pdf_to_docx_service.build_pdf_to_docx_settings(page_count=1)

        self.assertEqual(settings, {"multi_processing": False, "cpu_count": 1})

    def test_parallel_conversion_can_be_disabled_by_environment(self) -> None:
        with (
            patch.object(pdf_to_docx_service, "get_system_cpu_count", return_value=8),
            patch.dict(os.environ, {pdf_to_docx_service.DISABLE_PARALLEL_ENV: "1"}, clear=False),
        ):
            settings = pdf_to_docx_service.build_pdf_to_docx_settings(page_count=20)

        self.assertEqual(settings, {"multi_processing": False, "cpu_count": 1})

    def test_parallel_converter_uses_isolated_temp_files(self) -> None:
        seen_vectors = []
        seen_process_count = []

        class FakePool:
            def __init__(self, processes):
                seen_process_count.append(processes)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def map(self, func, vectors, chunksize):
                seen_vectors.extend(vectors)
                for vector in vectors:
                    Path(vector[7]).write_text("{}", encoding="utf-8")

        converter = pdf_to_docx_service.ParallelPdfToDocxConverter.__new__(
            pdf_to_docx_service.ParallelPdfToDocxConverter
        )
        converter.filename_pdf = "input.pdf"
        converter.password = ""
        converter.deserialize = Mock()
        converter.make_docx = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "output.docx"
            with (
                patch.object(pdf_to_docx_service, "Pool", FakePool),
                patch.object(pdf_to_docx_service, "get_system_cpu_count", return_value=8),
            ):
                converter._convert_with_multi_processing(
                    str(output_path),
                    0,
                    9,
                    multi_processing=True,
                    cpu_count=3,
                )

            json_paths = [Path(vector[7]) for vector in seen_vectors]

        self.assertEqual(seen_process_count, [3])
        self.assertEqual(len(json_paths), 3)
        self.assertTrue(all(path.is_absolute() for path in json_paths))
        self.assertTrue(all(path.name.startswith("pages-") for path in json_paths))
        self.assertTrue(all(path.parent.name.startswith("pdf2docx-") for path in json_paths))
        self.assertEqual(converter.deserialize.call_count, 3)
        converter.make_docx.assert_called_once()

    def test_complex_pdf_profile_uses_visual_conversion(self) -> None:
        profile = pdf_to_docx_service.PdfComplexityProfile(
            page_count=185,
            average_images_per_page=110,
            average_drawings_per_page=84,
        )

        with patch.dict(os.environ, {pdf_to_docx_service.MODE_ENV: "auto"}, clear=False):
            self.assertTrue(pdf_to_docx_service.should_use_visual_docx_conversion(profile))

    def test_editable_mode_keeps_pdf2docx_for_complex_pdf(self) -> None:
        profile = pdf_to_docx_service.PdfComplexityProfile(
            page_count=185,
            average_images_per_page=110,
            average_drawings_per_page=84,
        )

        with patch.dict(os.environ, {pdf_to_docx_service.MODE_ENV: "editable"}, clear=False):
            self.assertFalse(pdf_to_docx_service.should_use_visual_docx_conversion(profile))

    def test_visual_docx_conversion_embeds_one_image_per_page(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "source.pdf"
            output = temp_path / "output.docx"

            pdf = fitz.open()
            for page_number in range(2):
                page = pdf.new_page(width=300, height=420)
                page.insert_text((30, 40), f"Pagina {page_number + 1}", fontsize=12)
                page.draw_rect((30, 70, 270, 160), color=(0, 0, 0), width=0.5)
            pdf.save(source)
            pdf.close()

            pdf_to_docx_service.convert_pdf_to_visual_docx(source, output, dpi=72)

            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 0)
            with zipfile.ZipFile(output) as docx:
                media_files = [
                    name
                    for name in docx.namelist()
                    if name.startswith("word/media/") and name.endswith(".png")
                ]

        self.assertEqual(len(media_files), 2)


if __name__ == "__main__":
    unittest.main()
