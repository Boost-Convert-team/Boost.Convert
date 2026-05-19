from flask import Blueprint
from Blueprints.services.conversions.documents.pdf_to_jpg_service import convert_pdf_jpg
from Blueprints.handler_convertions import handle_conversion

pdf_jpg_bp = Blueprint("pdf_jpg",__name__)
@pdf_jpg_bp.route("/convert/pdf-to-jpg", methods=["POST"])
def pdf_to_jpg():
    return handle_conversion(
         allowed_extension=["pdf"]
        ,convert_function=convert_pdf_jpg
        ,output_extension="zip"
        ,tool_name="pdf_to_jpg"
    )