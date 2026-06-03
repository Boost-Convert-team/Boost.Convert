from PIL import Image
from Blueprints.services.convertions_services.conversion_option_values import get_image_quality

def convert_webp_jpg(input_path, output_path, options=None):
    with Image.open(input_path) as image:
        image.convert("RGB").save(
             output_path
            ,"JPEG"
            ,quality=get_image_quality(options or {})
            ,optimize=True
        )
