import pandas

def convert_csv_xlsx(input_path, output_path):
    dataframe = pandas.read_csv(input_path)
    dataframe.to_excel(output_path)