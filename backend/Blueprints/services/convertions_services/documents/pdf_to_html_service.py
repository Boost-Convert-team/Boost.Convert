import fitz

def convert_pdf_html(input_path, output_path):
    with fitz.open(input_path) as document: html = "\n".join(str(document[page_index].get_text("html")) for page_index in range(document.page_count))
    with open(output_path, "w", encoding="utf-8") as file: file.write(html)
