import pandas as pd
from docx import Document

def convert_excel_docx(input_path, output_path):
    document = Document()
    df = pd.read_excel(input_path)
    table = document.add_table(rows=1, cols=len(df.columns))

    for index, column in enumerate(df.columns):
        table.rows[0].cells[index].text = str(column)

    for _row_index, row in df.iterrows():
        cells = table.add_row().cells
        for index, value in enumerate(row):
            cells[index].text = str(value)

    document.save(output_path)
