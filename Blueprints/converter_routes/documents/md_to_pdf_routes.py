from flask import Blueprint
from Blueprints.services.conversions.documents.md_to_pdf_service import convert_markdown_pdf
from Blueprints.handler_convertions import handle_conversion

md_pdf_bp = Blueprint("md_pdf",__name__)
@md_pdf_bp.route("/convert/md-to-pdf", methods=["POST"])
def md_to_pdf():
    return handle_conversion(
         allowed_extension=["md"]
        ,convert_function=convert_markdown_pdf
        ,output_extension="pdf"
        ,tool_name="md_to_pdf"
    )