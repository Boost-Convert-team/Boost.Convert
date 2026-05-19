from flask import Blueprint
from Blueprints.handler_convertions import handle_pdf_collection_conversion
from Blueprints.services.conversions.documents.pdf_merge_service import convert_pdf_merge

pdf_merge_bp = Blueprint("pdf_merge", __name__)

@pdf_merge_bp.route("/convert/pdf-merge", methods=["POST"])
def pdf_merge():
    return handle_pdf_collection_conversion(
         convert_function=convert_pdf_merge
        ,output_extension="pdf"
        ,tool_name="pdf_merge"
    )
