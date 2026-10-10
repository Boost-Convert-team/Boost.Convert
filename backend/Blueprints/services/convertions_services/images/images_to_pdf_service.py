import io
import os

import pymupdf
from PIL import Image, ImageOps

from Blueprints.services.convertions_services.images.image_preservation import copy_pdf_compatible_image

EXIF_ORIENTATION = 0x0112
JPEG_QUALITY = 95
# Largest page side most PDF readers accept (200 inches at 72 points per inch).
MAX_PAGE_POINTS = 14400


def convert_images_pdf(input_path, output_path):
    """One page per image, in upload order, sized like the image.

    The PDF is built one image at a time, so memory holds a single decoded
    image instead of the whole upload. Upright JPEGs are embedded byte for
    byte; every other image is turned upright from its EXIF orientation,
    flattened on white and stored as a high-quality JPEG.
    """
    register_heif_support()
    image_paths = [
        os.path.join(input_path, filename)
        for filename in sorted(os.listdir(input_path))
        if os.path.isfile(os.path.join(input_path, filename))
    ]
    if not image_paths: raise ValueError("Envie pelo menos uma imagem.")

    with pymupdf.open() as document:
        for path in image_paths:
            width, height, stream = read_pdf_image(path)
            scale = min(1, MAX_PAGE_POINTS / max(width, height))
            page = document.new_page(width=width * scale, height=height * scale)
            page.insert_image(page.rect, stream=stream)
        document.save(output_path, garbage=3, deflate=True)


def read_pdf_image(path):
    with Image.open(path) as image:
        orientation = image.getexif().get(EXIF_ORIENTATION, 1)
        if image.format == "JPEG" and image.mode in {"RGB", "L"} and orientation == 1:
            with open(path, "rb") as file:
                return image.width, image.height, file.read()

        pdf_image = copy_pdf_compatible_image(ImageOps.exif_transpose(image))
        buffer = io.BytesIO()
        pdf_image.save(buffer, "JPEG", quality=JPEG_QUALITY)
        return pdf_image.width, pdf_image.height, buffer.getvalue()


def register_heif_support():
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
