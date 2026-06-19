from fpdf import FPDF
from Blueprints.services.convertions_services.documents.text_encoding_preservation import (
    encode_latin1_pdf_line,
    read_utf8_lines_preserving_text,
)

def convert_txt_pdf(input_path, output_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for line in read_utf8_lines_preserving_text(input_path):
        pdf.multi_cell(0, 8, encode_latin1_pdf_line(line, input_path))

    pdf.output(output_path)
