import json

def read_json_table(input_path):
    with open(input_path, "r", encoding="utf-8") as file: data = json.load(file)

    if isinstance(data, list): return data
    if isinstance(data, dict): 
        if isinstance(data.get("data"), list): return data.get("data")

        return [data]
    raise ValueError("JSON invalido para tabela.")
