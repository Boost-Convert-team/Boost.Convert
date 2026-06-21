import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.tools import ai_tools


class AiToolsTests(unittest.TestCase):
    def test_mp4_to_text_route_functions_are_removed(self) -> None:
        self.assertFalse(hasattr(ai_tools, "mp4_to_text"))
        self.assertFalse(hasattr(ai_tools, "mp4_to_text_download"))

    def test_document_analyzer_route_function_exists(self) -> None:
        self.assertTrue(hasattr(ai_tools, "document_analyzer"))

    def test_youtube_analyzer_audio_transcription_functions_are_removed(self) -> None:
        self.assertFalse(hasattr(ai_tools, "transcribe_file_with_openrouter"))
        self.assertFalse(hasattr(ai_tools, "get_openrouter_transcription_model"))


if __name__ == "__main__":
    unittest.main()
