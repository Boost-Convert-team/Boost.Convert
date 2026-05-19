from PIL import Image

def convert_jpg_png(input_path,output_path):
    img = Image.open(input_path).convert("RGB")
    img.save(output_path, "PNG")