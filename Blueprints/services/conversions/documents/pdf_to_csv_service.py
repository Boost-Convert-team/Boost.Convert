import fitz
import pandas as pd

def convert_pdf_csv(input_path, output_path):
    doc = fitz.open(input_path)

    try:
        dataframes = []

        for page in doc:
            tables = page.find_tables()

            for table in tables:
                df = table.to_pandas()
                dataframes.append(df)

        if dataframes:
            final_df = pd.concat(dataframes, ignore_index=True)
        else:
            final_df = extract_pdf_text_dataframe(doc)

        final_df.to_csv(output_path, index=False, encoding="utf-8")

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
