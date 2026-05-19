from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.documents.pdf_compress_service import convert_pdf_compress

pdf_compress_bp = Blueprint("pdf_compress", __name__)

@pdf_compress_bp.route("/convert/pdf-compress", methods=["POST"])
def pdf_compress():
    return handle_conversion(
         allowed_extension=["pdf"]
        ,convert_function=convert_pdf_compress
        ,output_extension="pdf"
        ,tool_name="pdf_compress"
    )
