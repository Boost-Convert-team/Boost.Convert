from flask import Blueprint
from Blueprints.services.conversions.documents.pdf_to_csv_service import convert_pdf_csv
from Blueprints.handler_convertions import handle_conversion

pdf_csv_bp = Blueprint("pdf_csv",__name__)
@pdf_csv_bp.route("/convert/pdf-to-csv", methods=["POST"])
def pdf_to_csv():
    return handle_conversion(
         allowed_extension=["pdf"]
        ,convert_function=convert_pdf_csv
        ,output_extension="csv"
        ,tool_name="pdf_to_csv"
    )