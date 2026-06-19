from docx import Document
from Blueprints.services.convertions_services.documents.text_encoding_preservation import read_utf8_lines_preserving_text

def convert_txt_docx(input_path, output_path):
    document = Document()

    for line in read_utf8_lines_preserving_text(input_path):
        document.add_paragraph(line.rstrip())

    document.save(output_path)
