import sys
import tempfile
import unittest
from pathlib import Path

import pymupdf
from PIL import Image

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from Blueprints.services.convertions_services.images.images_to_pdf_service import convert_images_pdf

EXIF_ORIENTATION = 0x0112


class ImagesToPdfServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.inputs = Path(self.directory.name) / "inputs"
        self.inputs.mkdir()
        self.output = Path(self.directory.name) / "out.pdf"

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_one_page_per_image_in_upload_order(self) -> None:
        for index, size in enumerate(((300, 200), (200, 300), (250, 250)), start=1):
            Image.new("RGB", size, (index * 60, 80, 120)).save(self.inputs / f"{index:03d}_input.jpg")

        convert_images_pdf(str(self.inputs), str(self.output))

        with pymupdf.open(self.output) as document:
            sizes = [(round(page.rect.width), round(page.rect.height)) for page in document]
        self.assertEqual(sizes, [(300, 200), (200, 300), (250, 250)])

    def test_upright_jpeg_is_embedded_without_recompression(self) -> None:
        source = self.inputs / "001_input.jpg"
        Image.effect_noise((320, 240), 60).convert("RGB").save(source, quality=88)

        convert_images_pdf(str(self.inputs), str(self.output))

        with pymupdf.open(self.output) as document:
            xref = document[0].get_images()[0][0]
            self.assertEqual(document.extract_image(xref)["image"], source.read_bytes())

    def test_exif_orientation_turns_the_photo_upright(self) -> None:
        exif = Image.Exif()
        exif[EXIF_ORIENTATION] = 6  # stored landscape, shown portrait
        Image.new("RGB", (400, 300), "white").save(self.inputs / "001_input.jpg", exif=exif.tobytes())

        convert_images_pdf(str(self.inputs), str(self.output))

        with pymupdf.open(self.output) as document:
            self.assertEqual((document[0].rect.width, document[0].rect.height), (300, 400))

    def test_transparent_png_is_flattened_on_white(self) -> None:
        image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        image.paste((240, 138, 36, 255), (0, 0, 50, 100))
        image.save(self.inputs / "001_input.png")

        convert_images_pdf(str(self.inputs), str(self.output))

        with pymupdf.open(self.output) as document:
            pixmap = document[0].get_pixmap()
        self.assertGreater(min(pixmap.pixel(90, 50)), 240)


if __name__ == "__main__":
    unittest.main()
