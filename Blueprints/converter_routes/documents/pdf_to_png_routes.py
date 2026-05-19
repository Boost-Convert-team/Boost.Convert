from flask import Blueprint
from Blueprints.services.conversions.documents.pdf_to_png_service import convert_pdf_png
from Blueprints.handler_convertions import handle_conversion

pdf_png_bp = Blueprint("pdf_png",__name__)
@pdf_png_bp.route("/convert/pdf-to-png", methods=["POST"])
def pdf_to_png():
    return handle_conversion(
         allowed_extension=["pdf"]
        ,convert_function=convert_pdf_png
        ,output_extension="zip"
        ,tool_name="pdf_to_png"
    )