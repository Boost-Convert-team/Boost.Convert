from flask import Blueprint
from Blueprints.services.conversions.documents.html_to_pdf_service import convert_html_pdf
from Blueprints.handler_convertions import handle_conversion

html_pdf_bp = Blueprint("html_pdf",__name__)
@html_pdf_bp.route("/convert/html-to-pdf", methods=["POST"])
def html_to_pdf():
    return handle_conversion(
         allowed_extension=["html"]
        ,convert_function=convert_html_pdf
        ,output_extension="pdf"
        ,tool_name="html_to_pdf"
    )