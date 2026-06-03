from PIL import Image

def convert_jpg_png(input_path, output_path, options=None):
    with Image.open(input_path) as image: image.save(output_path, "PNG")
