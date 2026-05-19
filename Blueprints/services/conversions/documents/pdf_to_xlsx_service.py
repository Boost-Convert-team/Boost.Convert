import fitz
import pandas as pd

def convert_pdf_xlsx(input_path, output_path):
    doc = fitz.open(input_path)

    try:
        with pd.ExcelWriter(output_path) as writer:
            sheet_count = 0

            for page_index, page in enumerate(doc, start=1):
                tables = page.find_tables()

                for table in tables:
                    df = table.to_pandas()
                    sheet_count += 1
                    sheet_name = f"Pag{page_index}_Tabela{sheet_count}"

                    df.to_excel(writer, sheet_name=sheet_name[:31], index=False)

            if sheet_count == 0:
                extract_pdf_text_dataframe(doc).to_excel(writer, sheet_name="Texto", index=False)

    finally:
        doc.close()

def extract_pdf_text_dataframe(doc):
    rows = []

    for page_index, page in enumerate(doc, start=1):
        text = page.get_text("text")

        for line in text.splitlines():
            line = line.strip()

            if line:
                rows.append({"pagina": page_index, "texto": line})

    if not rows:
        rows.append({"pagina": "", "texto": ""})

    return pd.DataFrame(rows)
