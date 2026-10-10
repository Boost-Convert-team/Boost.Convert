import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from Blueprints.services.access.access_service import FREE_PLAN, PRO_PLAN, is_pro_user
from Blueprints.services.convertions_services.conversion_rules.conversion_limits import (
    TOOL_FILE_COUNT_LIMITS,
    get_plan_limits,
    get_tool_limit_info,
    validate_multi_file_count,
)
from config import Config
from security import CSRF_FIELD_NAME, CSRF_SESSION_KEY, clear_rate_limit_state

# ilovepdf.com/pricing, October 2026: Merge PDF 25 / 500 and Image to PDF 20 / 80 files per task.
ILOVEPDF_FILE_COUNT_LIMITS = {
    "pdf_merge": {FREE_PLAN: 25, PRO_PLAN: 500},
    "images_to_pdf": {FREE_PLAN: 20, PRO_PLAN: 80},
}

FREE_USER = SimpleNamespace(plano=FREE_PLAN)
PRO_USER = SimpleNamespace(plano=PRO_PLAN)


def files(count):
    return [object()] * count


class PlanAccessTests(unittest.TestCase):
    def test_pro_comes_from_the_plan_stored_on_the_account(self) -> None:
        self.assertTrue(is_pro_user(PRO_USER))
        self.assertFalse(is_pro_user(FREE_USER))
        self.assertFalse(is_pro_user(None))
        self.assertFalse(is_pro_user(SimpleNamespace()))


class FileCountLimitTests(unittest.TestCase):
    def test_combining_tools_stay_20_to_30_percent_above_ilovepdf(self) -> None:
        for tool_name, theirs in ILOVEPDF_FILE_COUNT_LIMITS.items():
            for plan in (FREE_PLAN, PRO_PLAN):
                with self.subTest(tool=tool_name, plan=plan):
                    ratio = TOOL_FILE_COUNT_LIMITS[tool_name][plan] / theirs[plan]
                    self.assertGreaterEqual(ratio, 1.2)
                    self.assertLessEqual(ratio, 1.3)

    def test_each_combining_tool_enforces_its_own_limit(self) -> None:
        for tool_name, limits in TOOL_FILE_COUNT_LIMITS.items():
            for user, plan in ((FREE_USER, FREE_PLAN), (PRO_USER, PRO_PLAN)):
                limit = limits[plan]
                with self.subTest(tool=tool_name, plan=plan):
                    self.assertTrue(validate_multi_file_count(files(limit), user, tool_name)[0])
                    valid, message = validate_multi_file_count(files(limit + 1), user, tool_name)
                    self.assertFalse(valid)
                    self.assertIn(f"{limit} arquivos", message)

    def test_other_tools_keep_the_per_upload_limit(self) -> None:
        self.assertTrue(validate_multi_file_count(files(2), FREE_USER, "files_to_zip")[0])
        self.assertFalse(validate_multi_file_count(files(3), FREE_USER, "files_to_zip")[0])
        self.assertTrue(validate_multi_file_count(files(15), PRO_USER, "png_to_jpg")[0])
        self.assertFalse(validate_multi_file_count(files(16), PRO_USER, "png_to_jpg")[0])

    def test_tool_pages_show_the_limits_of_their_tool(self) -> None:
        merge = get_tool_limit_info({"route": "/convert/pdf-merge"})
        images = get_tool_limit_info({"route": "/convert/images-to-pdf"})
        other = get_tool_limit_info({"route": "/convert/png-to-jpg"})

        self.assertEqual((merge["free_file_count_limit"], merge["pro_file_count_limit"]), (32, 650))
        self.assertEqual((images["free_file_count_limit"], images["pro_file_count_limit"]), (25, 100))
        self.assertEqual((other["free_file_count_limit"], other["pro_file_count_limit"]), (2, 15))

    def test_plan_summary_uses_the_enforced_numbers(self) -> None:
        limits = get_plan_limits()

        self.assertEqual(limits[FREE_PLAN]["daily_conversions"], 10)
        self.assertIsNone(limits[PRO_PLAN]["daily_conversions"])
        self.assertEqual(limits[FREE_PLAN]["merge_pdf_files"], 32)
        self.assertEqual(limits[PRO_PLAN]["images_to_pdf_files"], 100)
        self.assertEqual(limits[PRO_PLAN]["upload_labels"]["videos"], "2 GB")


class PricingPageTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_rate_limit_state()
        Config.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        Config.SQLALCHEMY_ENGINE_OPTIONS = {}
        self.app = create_app()
        self.app.config.update(TESTING=True)
        with self.app.app_context():
            from extensions import db

            db.create_all()
        self.client = self.app.test_client()

    def test_pricing_page_has_limits_and_no_checkout(self) -> None:
        html = self.client.get("/planos").get_data(as_text=True)

        for text in ("Juntar at&eacute; 32 PDFs", "Juntar at&eacute; 650 PDFs",
                     "At&eacute; 25 imagens em um PDF", "At&eacute; 100 imagens em um PDF"):
            self.assertIn(text, html)
        self.assertIn("Em breve", html)
        for payment_word in ("Mercado Pago", "checkout", "Pagamento"):
            self.assertNotIn(payment_word, html)

    def test_free_user_over_the_merge_limit_sees_why_on_the_pricing_page(self) -> None:
        token = "test-csrf-token-with-enough-length-123"
        with self.client.session_transaction() as session:
            session[CSRF_SESSION_KEY] = token
        uploads = [(io.BytesIO(b"%PDF-1.4"), f"parte-{index}.pdf") for index in range(33)]

        response = self.client.post(
            "/convert/pdf-merge",
            data={CSRF_FIELD_NAME: token, "file": uploads},
            content_type="multipart/form-data",
            follow_redirects=True,
        )

        self.assertEqual(response.request.path, "/planos")
        self.assertIn("Limite do plano free: 32 arquivos", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
