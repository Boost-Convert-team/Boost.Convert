from docx.api import Document
import pandas as pd

def convert_docx_xlsx(input_path,output_path):
    document = Document(input_path)
    all_rows = []

    for table in document.tables:
        for row in table.rows:
            row_data = [cell.text for cell in row.cells]
            all_rows.append(row_data)

    df = pd.DataFrame(all_rows)
    df.to_excel(output_path, index=False)