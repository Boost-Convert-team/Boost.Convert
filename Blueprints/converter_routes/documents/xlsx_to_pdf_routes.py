from flask import Blueprint
from Blueprints.services.conversions.documents.xlsx_to_pdf_service import convert_excel_pdf
from Blueprints.handler_convertions import handle_conversion

xlsx_pdf_bp = Blueprint("xlsx_pdf",__name__)
@xlsx_pdf_bp.route("/convert/xlsx-to-pdf", methods=["POST"])
def xlsx_to_pdf():
    return handle_conversion(
         allowed_extension=["xlsx"]
        ,convert_function=convert_excel_pdf
        ,output_extension="pdf"
        ,tool_name="excel_to_pdf"
    )