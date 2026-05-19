from flask import Blueprint
from Blueprints.services.conversions.documents.json_to_xlsx_service import convert_json_xlsx
from Blueprints.handler_convertions import handle_conversion

json_xlsx_bp = Blueprint("json_xlsx",__name__)
@json_xlsx_bp.route("/convert/json-to-xlsx", methods=["POST"])
def json_to_xlsx():
    return handle_conversion(
         allowed_extension=["json"]
        ,convert_function=convert_json_xlsx
        ,output_extension="xlsx"
        ,tool_name="json_to_xlsx"
    )