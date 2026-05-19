from flask import Blueprint
from Blueprints.services.conversions.documents.csv_to_xlsx_service import convert_csv_xlsx
from Blueprints.handler_convertions import handle_conversion

csv_xlsx_bp = Blueprint("csv_xlsx",__name__)
@csv_xlsx_bp.route("/convert/csv-to-xlsx", methods=["POST"])
def csv_to_xlsx():
    return handle_conversion(
         allowed_extension=["csv"]
        ,convert_function=convert_csv_xlsx
        ,output_extension="xlsx"
        ,tool_name="csv_to_xlsx"
    )