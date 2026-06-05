import fitz

def convert_pdf_html(input_path, output_path):
    with fitz.open(input_path) as document: html = "\n".join(page.get_text("html") for page in document)
    with open(output_path, "w", encoding="utf-8") as file: file.write(html)
