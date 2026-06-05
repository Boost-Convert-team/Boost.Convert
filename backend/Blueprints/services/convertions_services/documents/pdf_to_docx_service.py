import fitz
from pdf2docx import Converter
from docx import Document

def convert_pdf_docx(input_path, output_path):
    try:
        converter = Converter(input_path)
        try:
            converter.convert(output_path)
        finally: converter.close()

    except Exception: 
        document = Document()

        with fitz.open(input_path) as pdf:
            for page_index in range(pdf.page_count):
                document.add_paragraph(str(pdf[page_index].get_text("text", sort=True)))

        document.save(output_path)
