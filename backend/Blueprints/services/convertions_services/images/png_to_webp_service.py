from PIL import Image
from Blueprints.services.convertions_services.conversion_option_values import get_image_quality

def convert_png_webp(input_path, output_path, options=None):
    with Image.open(input_path) as image:
        image.convert("RGB").save(
             output_path
            ,"WEBP"
            ,quality=get_image_quality(options or {})
            ,optimize=True
        )
