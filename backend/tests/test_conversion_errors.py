import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.convertions_services.errors.conversion_errors import (
    DEFAULT_CONVERSION_ERROR,
    build_friendly_conversion_error,
    get_user_friendly_conversion_error,
)


class ConversionErrorsTests(unittest.TestCase):
    def test_openrouter_placeholder_message_reaches_ui(self) -> None:
        message = "Configure OPENROUTER_API_KEY com uma chave real. Valor atual: prefixo 'cole_s', tamanho 24; esperado segredo da OpenRouter."

        friendly_message = get_user_friendly_conversion_error(RuntimeError(message))

        self.assertEqual(friendly_message, message)

    def test_openrouter_model_status_message_reaches_ui(self) -> None:
        message = "Erro na IA: status 404 no OpenRouter para modelo 'x/y:free'."

        friendly_message = get_user_friendly_conversion_error(RuntimeError(message))

        self.assertEqual(friendly_message, message)

    def test_empty_output_file_message_explains_next_step(self) -> None:
        friendly_error = build_friendly_conversion_error(RuntimeError("Arquivo final vazio."))

        self.assertEqual(friendly_error.title, "Arquivo convertido ficou vazio")
        self.assertIn("arquivo original", friendly_error.recovery)

    def test_missing_upload_message_guides_user_inside_boost(self) -> None:
        friendly_error = build_friendly_conversion_error(ValueError("Nenhum arquivo enviado"))

        self.assertEqual(friendly_error.title, "Nenhum arquivo selecionado")
        self.assertIn("nome do arquivo aparece", friendly_error.recovery)

    def test_large_request_message_uses_boost_language(self) -> None:
        friendly_error = build_friendly_conversion_error(ValueError("Arquivo maior que o limite geral."))

        self.assertEqual(friendly_error.title, "Arquivo grande demais")
        self.assertIn("limite aceito pelo Boost", friendly_error.message)

    def test_generic_processing_error_explains_preparation_failure(self) -> None:
        friendly_error = build_friendly_conversion_error(RuntimeError("Erro ao processar os arquivos."))

        self.assertEqual(friendly_error.title, "Erro ao preparar os arquivos")
        self.assertIn("preparar os arquivos enviados", friendly_error.message)

    def test_technical_message_hides_internal_path(self) -> None:
        error = RuntimeError(r"Traceback em C:\tmp\input.pdf: object has no attribute 'x'")

        friendly_message = get_user_friendly_conversion_error(error)

        self.assertEqual(friendly_message, DEFAULT_CONVERSION_ERROR)


if __name__ == "__main__":
    unittest.main()
