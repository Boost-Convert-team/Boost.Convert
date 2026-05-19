import json

import pandas


def read_json_as_dataframe(input_path):
    with open(input_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        if not data:
            return pandas.DataFrame([{"value": ""}])

        if all(isinstance(item, dict) for item in data):
            return pandas.json_normalize(data)

        return pandas.DataFrame({"value": data})

    if isinstance(data, dict):
        if not data:
            return pandas.DataFrame([{"value": ""}])

        if all(not isinstance(value, (dict, list)) for value in data.values()):
            return pandas.DataFrame([data])

        return pandas.json_normalize(data)

    return pandas.DataFrame([{"value": data}])
