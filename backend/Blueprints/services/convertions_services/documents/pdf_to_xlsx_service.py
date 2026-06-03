import fitz
import pandas as pd

def convert_pdf_xlsx(input_path, output_path):
    with fitz.open(input_path) as document: rows = [{"pagina": page.number + 1,"texto": page.get_text("text", sort=True)} for page in document]

    pd.DataFrame(rows).to_excel(output_path, index=False)
