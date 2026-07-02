import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from security import CSRF_FIELD_NAME, CSRF_SESSION_KEY


class ErrorPagesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def test_missing_browser_route_uses_boost_error_page(self) -> None:
        response = self.client.get("/rota-inexistente")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 404)
        self.assertIn("Boost.Convert", html)
        self.assertIn("P\u00e1gina n\u00e3o encontrada", html)

    def test_removed_external_downloader_routes_return_404(self) -> None:
        removed_tool_path = "/tools/" + "".join(("you", "tube")) + "-download"
        for path, method in (
            (removed_tool_path, self.client.get),
            (f"{removed_tool_path}/download", lambda url: self.client.post(url, data=self.csrf_data())),
        ):
            with self.subTest(path=path):
                response = method(path)

                self.assertEqual(response.status_code, 404)

    def test_api_missing_route_keeps_json_error(self) -> None:
        response = self.client.get("/api/rota-inexistente", headers={"Accept": "application/json"})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {"ok": False, "error": "Pagina nao encontrada."})

    def test_favicon_uses_boost_logo(self) -> None:
        response = self.client.get("/favicon.ico", buffered=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/svg+xml")
        self.assertIn("logo boost.svg", response.headers["Content-Disposition"])

    def test_upload_without_file_uses_boost_error_page(self) -> None:
        response = self.client.post("/convert/pdf-to-docx", data=self.csrf_data())
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Nenhum arquivo selecionado", html)
        self.assertIn("Escolher outra convers", html)

    def csrf_data(self, data: dict[str, str] | None = None) -> dict[str, str]:
        token = "test-csrf-token-with-enough-length-123"
        with self.client.session_transaction() as session:
            session[CSRF_SESSION_KEY] = token
        return {**(data or {}), CSRF_FIELD_NAME: token}


if __name__ == "__main__":
    unittest.main()
