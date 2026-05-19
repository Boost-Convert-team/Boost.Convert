from PIL import Image
from Blueprints.services.conversions.conversion_option_values import get_image_quality

def convert_webp_jpg(input_path, output_path, options=None):
    options = options or {}
    img = Image.open(input_path).convert("RGB")
    img.save(output_path, "JPEG", quality=get_image_quality(options), optimize=True)
