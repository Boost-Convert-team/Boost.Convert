from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.documents.txt_to_pdf_service import convert_txt_pdf

txt_pdf_bp = Blueprint("txt_pdf", __name__, url_prefix="/convert")
@txt_pdf_bp.route("/txt-to-pdf", methods=["POST"])
def txt_to_pdf():
    return handle_conversion(
         allowed_extension=["txt"]
        ,convert_function= convert_txt_pdf
        ,output_extension="pdf"
        ,tool_name="text_to_pdf"
    )