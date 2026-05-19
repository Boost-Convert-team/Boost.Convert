from Blueprints.services.conversions.documents.json_table_reader import read_json_as_dataframe

def convert_json_csv(input_path, output_path):
    dataframe = read_json_as_dataframe(input_path)
    dataframe.to_csv(output_path, index=False)
