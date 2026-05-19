from fpdf import FPDF

def convert_markdown_pdf(input_path, output_path):
    pdf = FPDF()
    pdf.add_page()

    with open(input_path, "r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()

            if not line:
                pdf.ln(4)
                continue

            if line.startswith("# "):
                pdf.set_font("Arial", "B", 18)
                pdf.multi_cell(0, 10, clean_markdown_line(line[2:]))
            elif line.startswith("## "):
                pdf.set_font("Arial", "B", 15)
                pdf.multi_cell(0, 9, clean_markdown_line(line[3:]))
            elif line.startswith("### "):
                pdf.set_font("Arial", "B", 13)
                pdf.multi_cell(0, 8, clean_markdown_line(line[4:]))
            else:
                pdf.set_font("Arial", "", 12)
                pdf.multi_cell(0, 8, clean_markdown_line(line))

    pdf.output(output_path)

def clean_markdown_line(line):
    return line.replace("**", "").replace("__", "").replace("*", "").replace("`", "")
