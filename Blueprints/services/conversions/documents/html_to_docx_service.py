from html2docx import html2docx

def convert_html_docx(input_path, output_path):
    with open(input_path, "r", encoding="utf-8") as file:
        html_content = file.read()

    docx_file = html2docx(html_content, title="Documento convertido")

    with open(output_path, "wb") as file:
        file.write(docx_file.getvalue())