from PIL import Image
from Blueprints.services.convertions_services.conversion_rules.conversion_option_values import (
    get_image_quality,
)
from Blueprints.services.convertions_services.images.image_preservation import save_jpeg_preserving_visual

def convert_png_jpg(input_path, output_path, options=None):
    with Image.open(input_path) as image:
        save_jpeg_preserving_visual(image, output_path, get_image_quality(options or {}))
