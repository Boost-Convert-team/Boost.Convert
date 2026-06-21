import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.tools import ai_tools
from register_blueprints import TOOLS_BLUEPRINTS


class AiToolsTests(unittest.TestCase):
    def test_ai_tools_blueprint_has_no_routes(self) -> None:
        self.assertEqual(ai_tools.ai_tools_bp.deferred_functions, [])

    def test_ai_tools_blueprint_is_not_registered(self) -> None:
        blueprint_names = [blueprint.name for blueprint in TOOLS_BLUEPRINTS]

        self.assertNotIn("ai_tools", blueprint_names)

    def test_ai_tool_route_functions_are_removed(self) -> None:
        self.assertFalse(hasattr(ai_tools, "document_analyzer"))
        self.assertFalse(hasattr(ai_tools, "youtube_analyzer"))
        self.assertFalse(hasattr(ai_tools, "mp4_to_text"))
        self.assertFalse(hasattr(ai_tools, "mp4_to_text_download"))
        self.assertFalse(hasattr(ai_tools, "transcribe_file_with_openrouter"))
        self.assertFalse(hasattr(ai_tools, "get_openrouter_transcription_model"))


if __name__ == "__main__":
    unittest.main()
