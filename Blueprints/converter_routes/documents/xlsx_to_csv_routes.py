from flask import Blueprint
from Blueprints.services.conversions.documents.xlsx_to_csv_service import convert_excel_csv
from Blueprints.handler_convertions import handle_conversion

xlsx_csv_bp = Blueprint("xlsx_csv",__name__)
@xlsx_csv_bp.route("/convert/xlsx-to-csv", methods=["POST"])
def xlsx_to_csv():
    return handle_conversion(
         allowed_extension=["xlsx"]
        ,convert_function=convert_excel_csv
        ,output_extension="csv"
        ,tool_name="excel_to_csv"
    )
