from flask import Blueprint
from Blueprints.services.conversions.documents.docx_to_txt_service import convert_docx_txt
from Blueprints.handler_convertions import handle_conversion

docx_txt_bp = Blueprint("docx_txt",__name__)
@docx_txt_bp.route("/convert/docx-to-txt", methods=["POST"])
def docx_to_txt():
    return handle_conversion(
         allowed_extension=["docx"]
        ,convert_function=convert_docx_txt
        ,output_extension="txt"
        ,tool_name="docx_to_txt"
    )