import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.main.tools_registry import (
    TOOLS,
    TOOL_DESCRIPTIONS,
    attach_tool_descriptions,
)


class ToolsRegistryTests(unittest.TestCase):
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
