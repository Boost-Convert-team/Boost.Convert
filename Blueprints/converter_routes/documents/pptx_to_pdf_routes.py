from flask import Blueprint
from Blueprints.services.conversions.documents.pptx_to_pdf_service import convert_pptx_pdf
from Blueprints.handler_convertions import handle_conversion

pptx_pdf_bp = Blueprint("pptx_pdf",__name__)
@pptx_pdf_bp.route("/convert/pptx-to-pdf", methods=["POST"])
def pptx_to_pdf():
    return handle_conversion(
         allowed_extension=["pptx"]
        ,convert_function=convert_pptx_pdf
        ,output_extension="pdf"
        ,tool_name="pptx_to_pdf"
    )