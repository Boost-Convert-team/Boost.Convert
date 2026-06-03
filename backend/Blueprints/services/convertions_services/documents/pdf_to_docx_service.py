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
            for page in pdf: document.add_paragraph(page.get_text("text", sort=True))

        document.save(output_path)
