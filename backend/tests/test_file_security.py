import sys
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

from werkzeug.datastructures import FileStorage


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from Blueprints.main.downloads import get_safe_download_path
from Blueprints.services.convertions_services.conversion_rules.conversion_limits import (
    validate_upload_size,
)
from Blueprints.services.convertions_services.documents.files_to_zip_service import secure_archive_filename
from Blueprints.services.convertions_services.runtime import ffmpeg_runner
from Blueprints.services.convertions_services.upload_flow.job_factory import create_single_conversion_job
from Blueprints.services.convertions_services.validation.file_security import validate_zip_file
from Blueprints.services.privacy.file_retention import get_conversions_root


class FileSecurityTests(unittest.TestCase):
    def test_upload_rejects_forbidden_extension(self) -> None:
        app = create_app()
        app.config.update(TESTING=True)
        file = FileStorage(stream=BytesIO(b"bad"), filename="payload.exe")

        with app.app_context():
            with self.assertRaisesRegex(ValueError, "Formato invalido"):
                create_single_conversion_job(file, None, "sid", {"pdf"}, "docx", "pdf_to_docx", {})

    def test_upload_size_rejects_file_above_plan_limit(self) -> None:
        file = FakeUploadFile(size=51 * 1024 * 1024)

        valid, message = validate_upload_size(file, None, "pdf", "docx")

        self.assertFalse(valid)
        self.assertIn("Arquivo muito grande", message)

    def test_zip_with_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "unsafe.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("../secret.txt", "x")

            valid, message = validate_zip_file(zip_path)

        self.assertFalse(valid)
        self.assertEqual(message, "Arquivo ZIP contem caminho inseguro.")

    def test_archive_filename_removes_path_segments(self) -> None:
        self.assertEqual(secure_archive_filename("../contrato.pdf"), "contrato.pdf")
        self.assertEqual(secure_archive_filename(""), "arquivo")

    def test_safe_download_path_requires_conversion_root(self) -> None:
        app = create_app()
        app.config.update(TESTING=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            outside_file = Path(temp_dir) / "outside.pdf"
            outside_file.write_text("x", encoding="utf-8")

            self.assertIsNone(get_safe_download_path(app, outside_file))

    def test_safe_download_path_accepts_private_conversion_file(self) -> None:
        app = create_app()
        app.config.update(TESTING=True)
        root = Path(get_conversions_root(app))
        output_file = root / "job" / "output.pdf"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text("x", encoding="utf-8")

        self.assertEqual(get_safe_download_path(app, output_file), str(output_file.resolve()))

    def test_run_ffmpeg_uses_list_command_timeout_and_no_shell(self) -> None:
        run = Mock()

        with (
            patch.object(ffmpeg_runner, "get_ffmpeg_command", return_value="ffmpeg"),
            patch.object(ffmpeg_runner.subprocess, "run", run),
        ):
            ffmpeg_runner.run_ffmpeg(["-i", "input.mp4", "output.mp3"])

        call_kwargs = run.call_args.kwargs
        self.assertEqual(run.call_args.args[0], ["ffmpeg", "-y", "-i", "input.mp4", "output.mp3"])
        self.assertEqual(call_kwargs["timeout"], 300)
        self.assertNotIn("shell", call_kwargs)

class FakeUploadFile:
    def __init__(self, size: int) -> None:
        self.stream = FakeSizedStream(size)


class FakeSizedStream:
    def __init__(self, size: int) -> None:
        self.size = size
        self.position = 0

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = 0) -> None:
        if whence == 2:
            self.position = self.size + offset
            return
        self.position = offset


if __name__ == "__main__":
    unittest.main()
