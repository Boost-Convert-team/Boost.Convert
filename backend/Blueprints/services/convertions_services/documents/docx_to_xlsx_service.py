import pandas as pd
from docx import Document

def convert_docx_xlsx(input_path, output_path):
    document = Document(input_path)
    pd.DataFrame({"texto": [paragraph.text for paragraph in document.paragraphs]}).to_excel(output_path, index=False)
