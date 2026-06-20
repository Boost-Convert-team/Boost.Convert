import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.converter_routes.registry import SIMPLE_CONVERTER_ROUTES
from register_blueprints import ALL_BLUEPRINTS


class OcrRemovedTests(unittest.TestCase):
    def test_ocr_converter_routes_are_not_generated(self) -> None:
        routes = [route.url_rule for route in SIMPLE_CONVERTER_ROUTES]

        self.assertNotIn("/convert/image-ocr-to-txt", routes)
        self.assertNotIn("/convert/pdf-ocr-to-txt", routes)
        self.assertNotIn("/convert/pdf-ocr-searchable", routes)

    def test_ocr_blueprints_are_not_registered(self) -> None:
        names = [blueprint.name for blueprint in ALL_BLUEPRINTS]

        self.assertFalse(any("ocr" in name for name in names))


if __name__ == "__main__":
    unittest.main()
