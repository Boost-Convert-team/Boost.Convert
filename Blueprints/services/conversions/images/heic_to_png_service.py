from PIL import Image
import pillow_heif

pillow_heif.register_heif_opener()

def convert_heic_png(input_path, output_path):
    with Image.open(input_path) as img:
        img.convert('RGB').save(output_path, 'PNG')   