import io
from PIL import Image
from Blueprints.services.convertions_services.images.image_preservation import save_jpeg_preserving_visual

def convert_svg_jpg(input_path, output_path):
    import fitz
    
    document = fitz.open(input_path)
    try:
        pixmap = document[0].get_pixmap(alpha=True)
        with Image.open(io.BytesIO(pixmap.tobytes("png"))) as image:
            save_jpeg_preserving_visual(image, output_path)
    finally:
        document.close()
