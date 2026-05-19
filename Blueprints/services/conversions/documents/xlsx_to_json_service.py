import pandas

def convert_excel_json(input_path, output_path):
    dataframe = pandas.read_excel(input_path)
    dataframe.to_json(output_path, orient="records")