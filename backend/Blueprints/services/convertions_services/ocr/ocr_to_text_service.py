import fitz

def convert_pdf_ocr_txt(input_path, output_path):
    with fitz.open(input_path) as document: text = "".join(page.get_text("text", sort=True) for page in document)

    with open(output_path, "w", encoding="utf-8") as file: file.write(text)

def convert_image_ocr_txt(input_path, output_path):
    with open(output_path, "w", encoding="utf-8") as file: file.write("")
