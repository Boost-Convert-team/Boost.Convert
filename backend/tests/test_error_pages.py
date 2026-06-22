import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app


class ErrorPagesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.app.config.update(TESTING=True)

    def test_missing_browser_route_uses_boost_error_page(self) -> None:
        response = self.app.test_client().get("/rota-inexistente")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 404)
        self.assertIn("Boost.Convert", html)
        self.assertIn("P\u00e1gina n\u00e3o encontrada", html)

    def test_api_missing_route_keeps_json_error(self) -> None:
        response = self.app.test_client().get("/api/rota-inexistente", headers={"Accept": "application/json"})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {"ok": False, "error": "Pagina nao encontrada."})

    def test_upload_without_file_uses_boost_error_page(self) -> None:
        response = self.app.test_client().post("/convert/pdf-to-docx", data={})
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Nenhum arquivo selecionado", html)
        self.assertIn("Escolher outra convers", html)


if __name__ == "__main__":
    unittest.main()
