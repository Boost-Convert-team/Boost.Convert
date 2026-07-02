import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.main.tools_registry import (
    TOOLS,
    TOOL_DESCRIPTIONS,
    attach_tool_descriptions,
    build_tool_counts,
)


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

    def test_ai_tools_are_not_listed(self) -> None:
        routes = [tool["route"] for tools in TOOLS.values() for tool in tools]
        names = [tool["name"] for tools in TOOLS.values() for tool in tools]

        self.assertNotIn("AI Tools", TOOLS)
        self.assertNotIn("/tools/ai/document-analyzer", routes)
        removed_brand = "".join(("You", "Tube"))
        removed_slug = removed_brand.lower()

        self.assertNotIn(f"/tools/ai/{removed_slug}-analyzer", routes)
        self.assertNotIn("Document Analyzer AI", names)
        self.assertFalse(any(removed_brand in name for name in names))

    def test_external_video_downloader_tool_is_not_listed(self) -> None:
        removed_tool_path = "/tools/" + "".join(("you", "tube")) + "-download"
        routes = [tool["route"] for tools in TOOLS.values() for tool in tools]

        self.assertNotIn(removed_tool_path, routes)
        self.assertNotIn(removed_tool_path, TOOL_DESCRIPTIONS)

    def test_tool_counts_do_not_include_ai_tools(self) -> None:
        counts = build_tool_counts()

        self.assertNotIn("AI Tools", counts["categories"])
        self.assertNotIn("AI Tools", counts["mega_totals"])
        self.assertNotIn("OCR", counts["categories"])
        self.assertNotIn("OCR", counts["mega_totals"])

    def test_every_tool_has_specific_description(self) -> None:
        missing_descriptions = [
            tool["route"]
            for category_tools in TOOLS.values()
            for tool in category_tools
            if not str(tool.get("description", "")).strip()
        ]

        self.assertEqual([], missing_descriptions)
        self.assertFalse(any("Aceita " in text for text in TOOL_DESCRIPTIONS.values()))

    def test_attach_tool_descriptions_adds_route_text(self) -> None:
        tools = {"Teste": [{"name": "Teste -> PDF", "route": "/convert/teste-to-pdf"}]}
        descriptions = {"/convert/teste-to-pdf": "Descricao didatica de teste."}

        attach_tool_descriptions(tools, descriptions)

        self.assertEqual("Descricao didatica de teste.", tools["Teste"][0]["description"])


if __name__ == "__main__":
    unittest.main()
