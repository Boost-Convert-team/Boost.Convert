import pandas

def convert_csv_md(input_path, output_path): pandas.read_csv(input_path).to_markdown(output_path)