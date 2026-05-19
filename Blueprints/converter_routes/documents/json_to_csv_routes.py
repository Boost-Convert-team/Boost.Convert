from flask import Blueprint
from Blueprints.services.conversions.documents.json_to_csv_service import convert_json_csv
from Blueprints.handler_convertions import handle_conversion

json_csv_bp = Blueprint("json_csv",__name__)
@json_csv_bp.route("/convert/json-to-csv", methods=["POST"])
def json_to_csv():
    return handle_conversion(
         allowed_extension=["json"]
        ,convert_function=convert_json_csv
        ,output_extension="csv"
        ,tool_name="json_to_csv"
    )