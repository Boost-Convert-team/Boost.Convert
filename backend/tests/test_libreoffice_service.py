import importlib
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.convertions_services.documents import libreoffice_service


CONVERTERS = (
    ("doc_to_docx_service", "convert_doc_docx", "docx"),
    ("doc_to_pdf_service", "convert_doc_pdf", "pdf"),
    ("odp_to_pdf_service", "convert_odp_pdf", "pdf"),
    ("odp_to_pptx_service", "convert_odp_pptx", "pptx"),
    ("ods_to_pdf_service", "convert_ods_pdf", "pdf"),
    ("ods_to_xlsx_service", "convert_ods_xlsx", "xlsx"),
    ("odt_to_docx_service", "convert_odt_docx", "docx"),
    ("odt_to_pdf_service", "convert_odt_pdf", "pdf"),
    ("ppt_to_pdf_service", "convert_ppt_pdf", "pdf"),
    ("ppt_to_pptx_service", "convert_ppt_pptx", "pptx"),
    ("pptx_to_pdf_service", "convert_pptx_pdf", "pdf"),
    ("xls_to_pdf_service", "convert_xls_pdf", "pdf"),
    ("xls_to_xlsx_service", "convert_xls_xlsx", "xlsx"),
    ("xlsx_to_pdf_service", "convert_excel_pdf", "pdf"),
)


def import_converter(module_name: str) -> types.ModuleType:
    return importlib.import_module(
        f"Blueprints.services.convertions_services.documents.{module_name}"
    )


class LibreOfficeServiceTests(unittest.TestCase):
    def test_find_office_converter_prefers_path_command(self) -> None:
        with patch.object(
            libreoffice_service.shutil,
            "which",
            return_value="/usr/bin/soffice",
        ) as which:
            converter = libreoffice_service.find_office_converter()

        self.assertEqual(converter, "/usr/bin/soffice")
        which.assert_called_once_with("soffice")

    def test_find_office_converter_uses_windows_fallback(self) -> None:
        with (
            patch.object(libreoffice_service.shutil, "which", return_value=None),
            patch.object(
                libreoffice_service.os.path,
                "exists",
                side_effect=[False, True],
            ),
        ):
            converter = libreoffice_service.find_office_converter()

        self.assertEqual(
            converter,
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        )

    def test_find_office_converter_raises_when_unavailable(self) -> None:
        with (
            patch.object(libreoffice_service.shutil, "which", return_value=None),
            patch.object(libreoffice_service.os.path, "exists", return_value=False),
        ):
            with self.assertRaisesRegex(RuntimeError, "LibreOffice nao encontrado"):
                libreoffice_service.find_office_converter()

    def test_find_converted_file_prefers_expected_filename(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            expected = Path(temp_dir) / "document.pdf"
            expected.touch()

            result = libreoffice_service.find_converted_file(
                temp_dir,
                "document.doc",
                "pdf",
            )

        self.assertEqual(result, str(expected))

    def test_find_converted_file_accepts_renamed_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            converted = Path(temp_dir) / "renamed.PDF"
            converted.touch()

            result = libreoffice_service.find_converted_file(
                temp_dir,
                "document.doc",
                "pdf",
            )

        self.assertEqual(result, str(converted))

    def test_run_libreoffice_conversion_preserves_command_and_move(self) -> None:
        run = Mock()
        move = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            converted_path = str(Path(temp_dir) / "document.pdf")
            temporary_directory = MagicMock()
            temporary_directory.__enter__.return_value = temp_dir
            temporary_directory.__exit__.return_value = False

            with (
                patch.object(
                    libreoffice_service,
                    "find_office_converter",
                    return_value="soffice",
                ),
                patch.object(
                    libreoffice_service,
                    "find_converted_file",
                    return_value=converted_path,
                ) as find_converted,
                patch.object(
                    libreoffice_service.tempfile,
                    "TemporaryDirectory",
                    return_value=temporary_directory,
                ),
                patch.object(libreoffice_service.subprocess, "run", run),
                patch.object(libreoffice_service.shutil, "move", move),
            ):
                libreoffice_service.run_libreoffice_conversion(
                    "document.doc",
                    "document.pdf",
                    "pdf",
                )

        run.assert_called_once_with(
            [
                "soffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                temp_dir,
                "document.doc",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=300,
        )
        find_converted.assert_called_once_with(temp_dir, "document.doc", "pdf")
        move.assert_called_once_with(converted_path, "document.pdf")

    def test_run_libreoffice_conversion_translates_process_error(self) -> None:
        with (
            patch.object(
                libreoffice_service,
                "find_office_converter",
                return_value="soffice",
            ),
            patch.object(
                libreoffice_service.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(1, ["soffice"]),
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Nao foi possivel converter este arquivo com LibreOffice",
            ):
                libreoffice_service.run_libreoffice_conversion(
                    "document.doc",
                    "document.pdf",
                    "pdf",
                )

    def test_run_libreoffice_conversion_falls_back_for_docx_without_office(self) -> None:
        fallback = Mock(return_value=True)

        with (
            patch.object(
                libreoffice_service,
                "find_office_converter",
                side_effect=RuntimeError("LibreOffice nao encontrado."),
            ),
            patch.object(libreoffice_service, "run_python_office_pdf_fallback", fallback),
        ):
            libreoffice_service.run_libreoffice_conversion(
                "document.docx",
                "document.pdf",
                "pdf",
            )

        fallback.assert_called_once_with("document.docx", "document.pdf", "pdf")

    def test_run_libreoffice_conversion_falls_back_for_xlsx_without_office(self) -> None:
        fallback = Mock(return_value=True)

        with (
            patch.object(
                libreoffice_service,
                "find_office_converter",
                side_effect=RuntimeError("LibreOffice nao encontrado."),
            ),
            patch.object(libreoffice_service, "run_python_office_pdf_fallback", fallback),
        ):
            libreoffice_service.run_libreoffice_conversion(
                "spreadsheet.xlsx",
                "spreadsheet.pdf",
                "pdf",
            )

        fallback.assert_called_once_with("spreadsheet.xlsx", "spreadsheet.pdf", "pdf")

    def test_converter_entry_points_delegate_to_shared_service(self) -> None:
        for module_name, function_name, extension in CONVERTERS:
            if module_name == "xlsx_to_pdf_service":
                continue
            with self.subTest(module=module_name):
                module = import_converter(module_name)
                runner = Mock()

                with patch.object(module, "run_libreoffice_conversion", runner):
                    getattr(module, function_name)("input.file", "output.file")

                runner.assert_called_once_with(
                    "input.file",
                    "output.file",
                    extension,
                )

    def test_converter_modules_keep_existing_helper_names(self) -> None:
        module_names = [name for name, _function, _extension in CONVERTERS]
        module_names.append("docx_to_pdf_service")

        for module_name in module_names:
            with self.subTest(module=module_name):
                module = import_converter(module_name)
                self.assertIs(
                    module.run_libreoffice_conversion,
                    libreoffice_service.run_libreoffice_conversion,
                )
                self.assertIs(
                    module.find_office_converter,
                    libreoffice_service.find_office_converter,
                )
                self.assertIs(
                    module.find_converted_file,
                    libreoffice_service.find_converted_file,
                )

    def test_docx_converter_keeps_libreoffice_fallback(self) -> None:
        module = import_converter("docx_to_pdf_service")
        runner = Mock()

        with (
            patch.object(
                module,
                "convert_docx_to_pdf_fallback",
                side_effect=RuntimeError("fallback failed"),
            ),
            patch.object(module, "run_libreoffice_conversion", runner),
            patch.object(module, "_has_pdf_output", return_value=True),
        ):
            module.convert_docx_pdf("input.docx", "output.pdf")

        runner.assert_called_once_with("input.docx", "output.pdf", "pdf")

    def test_docx_converter_uses_python_fallback_without_office(self) -> None:
        module = import_converter("docx_to_pdf_service")
        fallback = Mock()
        runner = Mock(side_effect=RuntimeError("LibreOffice nao encontrado."))

        with (
            patch.object(module, "run_libreoffice_conversion", runner),
            patch.object(module, "convert_docx_to_pdf_fallback", fallback),
            patch.object(module, "_has_pdf_output", return_value=True),
        ):
            module.convert_docx_pdf("input.docx", "output.pdf")

        fallback.assert_called_once_with("input.docx", "output.pdf")
        runner.assert_not_called()

    def test_xlsx_converter_uses_python_fallback_without_office(self) -> None:
        module = import_converter("xlsx_to_pdf_service")
        fallback = Mock()
        runner = Mock(side_effect=RuntimeError("LibreOffice nao encontrado."))

        with (
            patch.object(module, "run_libreoffice_conversion", runner),
            patch.object(module, "convert_xlsx_to_pdf_fallback", fallback),
        ):
            module.convert_excel_pdf("input.xlsx", "output.pdf")

        fallback.assert_called_once_with("input.xlsx", "output.pdf")
        runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
