from docx import Document

def convert_docx_txt(input_path, output_path):
    document = Document(input_path)

    with open(output_path, "w", encoding="utf-8") as file: file.write("\n".join(paragraph.text for paragraph in document.paragraphs))
