import os
from PIL import Image
from Blueprints.services.convertions_services.images.image_preservation import save_jpeg_preserving_visual

def convert_svg_jpg(input_path, output_path):
    import fitz
    
    document = fitz.open(input_path)
    try:
        temp_path = output_path + ".png"
        pixmap = document[0].get_pixmap(alpha=True)
        pixmap.save(temp_path)

        with Image.open(temp_path) as image:
            save_jpeg_preserving_visual(image, output_path)

        os.remove(temp_path)
    finally:
        document.close()
