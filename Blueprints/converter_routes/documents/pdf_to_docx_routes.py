from flask import Blueprint
from Blueprints.services.conversions.documents.pdf_to_docx_service import convert_pdf_docx
from Blueprints.handler_convertions import handle_conversion

pdf_docx_bp = Blueprint("pdf_docx",__name__)
@pdf_docx_bp.route("/convert/pdf-to-docx", methods=["POST"])
def pdf_to_docx():
    return handle_conversion(
         allowed_extension=["pdf"]
        ,convert_function=convert_pdf_docx
        ,output_extension="docx"
        ,tool_name="pdf_to_docx"
    )