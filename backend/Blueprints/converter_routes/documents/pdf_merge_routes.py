from flask import Blueprint
from Blueprints.handlers.conversion_handlers import handle_pdf_collection_conversion
from Blueprints.services.convertions_services.documents.pdf_merge_service import convert_pdf_merge

pdf_merge_bp = Blueprint("pdf_merge", __name__, url_prefix="/convert")
@pdf_merge_bp.route("/pdf-merge", methods=["POST"])
def pdf_merge():
    return handle_pdf_collection_conversion(
         convert_function=convert_pdf_merge
        ,output_extension="pdf"
        ,tool_name="pdf_merge"
    )
