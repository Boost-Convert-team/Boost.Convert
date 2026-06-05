import fitz
import pandas as pd

def convert_pdf_xlsx(input_path, output_path):
    with fitz.open(input_path) as document: rows = [{"pagina": page_index + 1,"texto": str(document[page_index].get_text("text", sort=True))} for page_index in range(document.page_count)]

    pd.DataFrame(rows).to_excel(output_path, index=False)
