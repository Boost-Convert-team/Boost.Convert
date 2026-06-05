import pandas as pd

def convert_excel_json(input_path, output_path):
    json_text = pd.read_excel(input_path).to_json(
         orient="records"
        ,force_ascii=False
        ,indent=2
    )

    with open(output_path, "w", encoding="utf-8") as file: file.write(json_text or "[]")
