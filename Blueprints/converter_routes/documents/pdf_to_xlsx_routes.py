from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.documents.pdf_to_xlsx_service import convert_pdf_xlsx

pdf_xlsx_bp = Blueprint("pdf_xlsx", __name__, url_prefix="/convert")
@pdf_xlsx_bp.route("/pdf-to-xlsx", methods=["POST"])
def pdf_to_xlsx():
    return handle_conversion(
         allowed_extension=["pdf"]
        ,convert_function= convert_pdf_xlsx
        ,output_extension="xlsx"
        ,tool_name="pdf_to_xlsx"
    )