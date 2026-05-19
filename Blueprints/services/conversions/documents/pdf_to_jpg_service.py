import fitz
import os
import tempfile
import zipfile
from PIL import Image
from Blueprints.services.conversions.conversion_option_values import get_pdf_render_zoom

def convert_pdf_jpg(input_path, output_path):
    zoom = get_pdf_render_zoom()

    with fitz.open(input_path) as document:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_paths = []

            for page_index, page in enumerate(document, start=1):
                pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                png_path = os.path.join(temp_dir, f"page_{page_index}.png")
                jpg_path = os.path.join(temp_dir, f"page_{page_index}.jpg")
                pixmap.save(png_path)

                with Image.open(png_path) as image:
                    image.convert("RGB").save(jpg_path, "JPEG", quality=90, optimize=True)

                image_paths.append(jpg_path)

            with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
                for image_path in image_paths:
                    zip_file.write(image_path, os.path.basename(image_path))
