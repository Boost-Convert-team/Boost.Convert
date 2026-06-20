import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.main.tools_registry import TOOLS, build_tool_counts


class ToolsRegistryTests(unittest.TestCase):
    def test_mp4_to_text_tool_is_not_listed(self) -> None:
        routes = [tool["route"] for tools in TOOLS.values() for tool in tools]
        names = [tool["name"] for tools in TOOLS.values() for tool in tools]

        self.assertNotIn("/tools/ai/mp4-to-text", routes)
        self.assertNotIn("MP4 para texto", names)

    def test_ocr_tools_are_not_listed(self) -> None:
        routes = [tool["route"] for tools in TOOLS.values() for tool in tools]
        names = [tool["name"] for tools in TOOLS.values() for tool in tools]

        self.assertNotIn("OCR", TOOLS)
        self.assertNotIn("/convert/image-ocr-to-txt", routes)
        self.assertNotIn("/convert/pdf-ocr-to-txt", routes)
        self.assertNotIn("/convert/pdf-ocr-searchable", routes)
        self.assertFalse(any("OCR" in name for name in names))

    def test_document_analyzer_tool_is_listed(self) -> None:
        routes = [tool["route"] for tools in TOOLS.values() for tool in tools]
        names = [tool["name"] for tools in TOOLS.values() for tool in tools]

        self.assertIn("/tools/ai/document-analyzer", routes)
        self.assertIn("Document Analyzer AI", names)

    def test_ai_tools_count_matches_remaining_tools(self) -> None:
        counts = build_tool_counts()

        self.assertEqual(counts["categories"]["AI Tools"], 2)
        self.assertEqual(counts["mega_totals"]["AI Tools"], 2)
        self.assertNotIn("OCR", counts["categories"])
        self.assertNotIn("OCR", counts["mega_totals"])


if __name__ == "__main__":
    unittest.main()
