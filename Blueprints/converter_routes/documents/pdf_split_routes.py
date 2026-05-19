from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.documents.pdf_split_service import convert_pdf_split

pdf_split_bp = Blueprint("pdf_split", __name__)

@pdf_split_bp.route("/convert/pdf-split", methods=["POST"])
def pdf_split():
    return handle_conversion(
         allowed_extension=["pdf"]
        ,convert_function=convert_pdf_split
        ,output_extension="zip"
        ,tool_name="pdf_split"
    )
