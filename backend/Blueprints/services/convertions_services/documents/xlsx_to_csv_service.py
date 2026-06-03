import pandas as pd

def convert_excel_csv(input_path, output_path): pd.read_excel(input_path).to_csv(output_path, index=False)
