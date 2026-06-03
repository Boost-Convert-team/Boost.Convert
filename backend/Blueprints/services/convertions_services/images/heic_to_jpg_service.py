from PIL import Image
from Blueprints.services.convertions_services.conversion_option_values import get_image_quality

def convert_heic_jpg(input_path, output_path, options=None):
    register_heif_support()

    with Image.open(input_path) as image:
        image.convert("RGB").save(
             output_path
            ,"JPEG"
            ,quality=get_image_quality(options or {})
            ,optimize=True
        )

def register_heif_support():
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
