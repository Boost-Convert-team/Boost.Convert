from PIL import Image

def convert_jpg_pdf(input_path, output_path): 
    with Image.open(input_path) as image: image.convert("RGB").save(output_path, "PDF")
