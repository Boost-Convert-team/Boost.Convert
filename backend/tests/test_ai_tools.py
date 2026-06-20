import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.tools import ai_tools


class FakeOpenRouterTranscriptionResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self.payload = payload

    def json(self) -> object:
        if isinstance(self.payload, ValueError):
            raise self.payload
        return self.payload


class AiToolsTests(unittest.TestCase):
    def test_mp4_to_text_route_functions_are_removed(self) -> None:
        self.assertFalse(hasattr(ai_tools, "mp4_to_text"))
        self.assertFalse(hasattr(ai_tools, "mp4_to_text_download"))

    def test_document_analyzer_route_function_exists(self) -> None:
        self.assertTrue(hasattr(ai_tools, "document_analyzer"))

    def test_get_openrouter_transcription_model_uses_default(self) -> None:
        with patch.dict(os.environ, {"OPENROUTER_TRANSCRIPTION_MODEL": ""}):
            model = ai_tools.get_openrouter_transcription_model()

        self.assertEqual(model, "qwen/qwen3-asr-flash-2026-02-10")

    def test_get_openrouter_transcription_model_uses_env(self) -> None:
        with patch.dict(os.environ, {"OPENROUTER_TRANSCRIPTION_MODEL": "openai/whisper-1"}):
            model = ai_tools.get_openrouter_transcription_model()

        self.assertEqual(model, "openai/whisper-1")

    def test_build_openrouter_transcription_payment_error_names_balance(self) -> None:
        response = FakeOpenRouterTranscriptionResponse(402, {"error": {"message": "pay"}})

        message = ai_tools.build_openrouter_transcription_payment_error(response)

        self.assertIn("saldo insuficiente", message)
        self.assertIn("US$0.50", message)

    def test_extract_openrouter_error_message_reads_json_error(self) -> None:
        response = FakeOpenRouterTranscriptionResponse(
            400,
            {"error": {"message": "formato invalido"}},
        )

        message = ai_tools.extract_openrouter_error_message(response)

        self.assertEqual(message, "formato invalido")


if __name__ == "__main__":
    unittest.main()
