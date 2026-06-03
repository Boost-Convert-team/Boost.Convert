import os
from PIL import Image

def convert_svg_jpg(input_path, output_path):
    import fitz
    
    document = fitz.open(input_path)
    try:
        temp_path = output_path + ".png"
        pixmap = document[0].get_pixmap(alpha=False)
        pixmap.save(temp_path)

        with Image.open(temp_path) as image:
            image.convert("RGB").save(output_path, "JPEG", quality=90, optimize=True)

        os.remove(temp_path)
    finally:
        document.close()
