from PIL import Image

def convert_heic_png(input_path, output_path, options=None):
    register_heif_support()

    with Image.open(input_path) as image:
        image.save(output_path, "PNG")

def register_heif_support():
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
