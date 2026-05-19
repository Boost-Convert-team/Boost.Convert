from PIL import Image
import pillow_heif
from Blueprints.services.conversions.conversion_option_values import get_image_quality

pillow_heif.register_heif_opener()

def convert_heic_jpg(input_path, output_path, options=None):
    options = options or {}

    with Image.open(input_path) as img:
        img.convert('RGB').save(output_path, 'JPEG', quality=get_image_quality(options), optimize=True)
