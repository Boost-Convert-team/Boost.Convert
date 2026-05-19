from flask import Blueprint
from Blueprints.services.conversions.documents.xlsx_to_json_service import convert_excel_json
from Blueprints.handler_convertions import handle_conversion

xlsx_json_bp = Blueprint("xlsx_json",__name__)
@xlsx_json_bp.route("/convert/xlsx-to-json", methods=["POST"])
def xlsx_to_json():
    return handle_conversion(
         allowed_extension=["xlsx"]
        ,convert_function=convert_excel_json
        ,output_extension="json"
        ,tool_name="excel_to_json"
    )