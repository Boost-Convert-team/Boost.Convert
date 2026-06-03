from flask import Blueprint
from Blueprints.handlers.conversion_handlers import handle_file_collection_conversion
from Blueprints.services.convertions_services.images.images_to_pdf_service import convert_images_pdf

images_pdf_bp = Blueprint("images_pdf", __name__, url_prefix="/convert")
@images_pdf_bp.route("/images-to-pdf", methods=["POST"])
def images_pdf():
    return handle_file_collection_conversion(
         allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'heic']
        ,convert_function=convert_images_pdf
        ,output_extension="pdf"
        ,tool_name="images_to_pdf"
        ,output_filename="imagens.pdf"
        ,original_label="Imagens para PDF"
    )
