from Blueprints.services.conversions.documents.json_table_reader import read_json_as_dataframe

def convert_json_xlsx(input_path, output_path):
    dataframe = read_json_as_dataframe(input_path)
    dataframe.to_excel(output_path, index=False)
