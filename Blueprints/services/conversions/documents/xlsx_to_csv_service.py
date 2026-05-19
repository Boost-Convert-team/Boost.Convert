import pandas

def convert_excel_csv(input_path, ouput_path):
    dataframe = pandas.read_excel(input_path)
    dataframe.to_csv(ouput_path, index=False)