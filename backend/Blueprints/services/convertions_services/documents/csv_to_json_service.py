import pandas

def convert_csv_json(input_path, output_path): pandas.read_csv(input_path).to_json(output_path)