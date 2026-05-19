from PIL import Image

def convert_jpg_pdf(input_path, output_path):
    image = Image.open(input_path)
    
    if image.mode != "RGB":
        image = image.convert("RGB") # metodo de imagem

    image.save(output_path, "PDF")