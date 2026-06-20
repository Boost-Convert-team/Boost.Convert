import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.convertions_services.errors.conversion_errors import (
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


if __name__ == "__main__":
    unittest.main()
