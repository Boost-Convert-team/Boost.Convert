from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.documents.pdf_edit_service import convert_pdf_edit

pdf_edit_bp = Blueprint("pdf_edit", __name__)

@pdf_edit_bp.route("/convert/pdf-edit", methods=["POST"])
def pdf_edit():
    return handle_conversion(
         allowed_extension=["pdf"]
        ,convert_function=convert_pdf_edit
        ,output_extension="pdf"
        ,tool_name="pdf_edit"
    )
