from flask import Blueprint
from Blueprints.services.conversions.documents.pdf_to_html_service import convert_pdf_html
from Blueprints.handler_convertions import handle_conversion

pdf_html_bp = Blueprint("pdf_html",__name__)
@pdf_html_bp.route("/convert/pdf-to-html", methods=["POST"])
def pdf_to_html():
    return handle_conversion(
         allowed_extension=["pdf"]
        ,convert_function=convert_pdf_html
        ,output_extension="html"
        ,tool_name="pdf_to_html"
    )