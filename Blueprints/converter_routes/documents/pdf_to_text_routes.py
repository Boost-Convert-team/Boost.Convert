from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.documents.pdf_to_text_service import convert_pdf_txt

pdf_txt_bp = Blueprint("pdf_txt", __name__, url_prefix="/convert")
@pdf_txt_bp.route("/pdf-to-txt", methods=["POST"])
def pdf_to_text():
    return handle_conversion(
         allowed_extension=["pdf"]
        ,convert_function= convert_pdf_txt
        ,output_extension="txt"
        ,tool_name="pdf_to_txt"
    )
