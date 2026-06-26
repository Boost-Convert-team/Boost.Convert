import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from Blueprints.handlers.conversion_handlers import handle_conversion_error, validate_uploaded_file_count
from Blueprints.services.convertions_services.upload_flow.job_factory import validate_single_file_upload
from Blueprints.services.subscription.access_service import UpgradeRequiredError
from security import CSRF_FIELD_NAME, CSRF_SESSION_KEY, clear_rate_limit_state


class SubscriptionRedirectTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_rate_limit_state()
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def test_anonymous_checkout_redirects_to_login(self) -> None:
        response = self.client.post("/checkout/pro", data=self.csrf_data())

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_upgrade_required_redirects_to_planos(self) -> None:
        with self.app.test_request_context("/convert/pdf-to-docx", method="POST"):
            response = handle_conversion_error(
                UpgradeRequiredError("Voce atingiu o limite de 10 conversoes."),
                "Arquivo recusado: %s",
                "Erro ao criar jobs",
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/planos")

    def test_free_file_count_limit_requires_upgrade(self) -> None:
        with self.assertRaises(UpgradeRequiredError):
            validate_uploaded_file_count([object(), object(), object()], None)

    def test_free_upload_size_limit_requires_upgrade(self) -> None:
        file = FakeUploadFile(size=51 * 1024 * 1024)

        with self.assertRaises(UpgradeRequiredError):
            validate_single_file_upload(file, None, "pdf", "docx")

    def test_pro_upload_size_limit_keeps_validation_error(self) -> None:
        file = FakeUploadFile(size=301 * 1024 * 1024)

        with self.assertRaises(ValueError):
            validate_single_file_upload(file, FakeProUser(), "pdf", "docx")

    def csrf_data(self) -> dict[str, str]:
        token = "test-csrf-token-with-enough-length-123"
        with self.client.session_transaction() as session:
            session[CSRF_SESSION_KEY] = token
        return {CSRF_FIELD_NAME: token}


class FakeProUser:
    plano = "pro"
    status_assinatura = "active"


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
