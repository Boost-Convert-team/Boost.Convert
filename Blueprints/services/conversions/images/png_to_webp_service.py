from PIL import Image
from Blueprints.services.conversions.conversion_option_values import get_image_quality

def convert_png_webp(input_path, output_path, options=None):
    options = options or {}
    img = Image.open(input_path).convert("RGB")
    img.save(output_path, "WEBP", quality=get_image_quality(options), method=6)
