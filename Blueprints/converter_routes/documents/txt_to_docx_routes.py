from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.documents.txt_to_docx_service import convert_txt_docx

txt_docx_bp = Blueprint("txt_docx", __name__, url_prefix="/convert")
@txt_docx_bp.route("/txt-to-docx", methods=["POST"])
def txt_to_docx():
    return handle_conversion(
         allowed_extension=["txt"]
        ,convert_function= convert_txt_docx
        ,output_extension="docx"
        ,tool_name="text_to_docx"
    )
