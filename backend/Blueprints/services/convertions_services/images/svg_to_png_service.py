import fitz

def convert_svg_png(input_path, output_path):
    document = fitz.open(input_path)
    try:
        pixmap = document[0].get_pixmap(alpha=False)
        pixmap.save(output_path)
    finally:
        document.close()
