import pandas as pd

def convert_csv_xlsx(input_path, output_path): pd.read_csv(input_path).to_excel(output_path, index=False)
