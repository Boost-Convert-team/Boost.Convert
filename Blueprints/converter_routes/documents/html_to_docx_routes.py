from flask import Blueprint
from Blueprints.services.conversions.documents.html_to_docx_service import convert_html_docx
from Blueprints.handler_convertions import handle_conversion

html_docx_bp = Blueprint("html_docx",__name__)
@html_docx_bp.route("/convert/html-to-docx", methods=["POST"])
def html_to_docx():
    return handle_conversion(
         allowed_extension=["html"]
        ,convert_function=convert_html_docx
        ,output_extension="docx"
        ,tool_name="html_to_docx"
    )