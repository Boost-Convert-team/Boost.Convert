from flask import Blueprint
from Blueprints.services.conversions.documents.jpg_to_pdf_service import convert_jpg_pdf
from Blueprints.handler_convertions import handle_conversion

jpg_pdf_bp = Blueprint("jpg_pdf",__name__)
@jpg_pdf_bp.route("/convert/jpg-to-pdf", methods=["POST"])
def jpg_to_pdf():
    return handle_conversion(
         allowed_extension=["jpg"]
        ,convert_function=convert_jpg_pdf
        ,output_extension="pdf"
        ,tool_name="jpg_to_pdf"
    )