from docx import Document

def convert_markdown_docx(input_path, output_path):
    document = Document()

    with open(input_path, "r", encoding="utf-8", errors="ignore") as file:
        for line in file: document.add_paragraph(line.rstrip())

    document.save(output_path)
