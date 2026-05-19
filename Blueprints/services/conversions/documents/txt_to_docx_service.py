from docx import Document

def convert_txt_docx(input_path, output_path):
    docx = Document()

    with open(input_path, "r", encoding="utf-8") as file:
        for line in file:
            docx.add_paragraph(line.strip())

    docx.save(output_path)