import pandas as pd

def convert_json_csv(input_path, output_path): pd.read_json(input_path).to_csv(output_path, index=False)
