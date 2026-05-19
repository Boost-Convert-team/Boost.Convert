from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.documents.docx_to_pdf_service import convert_docx_pdf

docx_pdf_bp = Blueprint("docx_pdf",__name__)
@docx_pdf_bp.route("/convert/docx-to-pdf", methods=["POST"])
def docx_to_pdf():
    return handle_conversion(
         allowed_extension=["docx"]
        ,convert_function=convert_docx_pdf
        ,output_extension="pdf"
        ,tool_name="docx_to_pdf"
    )