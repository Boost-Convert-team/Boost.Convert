from PIL import Image
from Blueprints.services.convertions_services.images.image_preservation import save_webp_lossless

def convert_png_webp(input_path, output_path, options=None):
    with Image.open(input_path) as image:
        save_webp_lossless(image, output_path)
