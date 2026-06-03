import pandas as pd

def convert_json_xlsx(input_path, output_path): pd.read_json(input_path).to_excel(output_path, index=False)
