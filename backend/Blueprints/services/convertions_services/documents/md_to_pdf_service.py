from fpdf import FPDF

def convert_markdown_pdf(input_path, output_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    with open(input_path, "r", encoding="utf-8", errors="ignore") as file:
        for line in file: pdf.multi_cell(0, 8, line.encode("latin-1", errors="replace").decode("latin-1"))

    pdf.output(output_path)
