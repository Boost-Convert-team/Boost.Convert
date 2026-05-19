from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.images.heic_to_jpg_service import convert_heic_jpg

heic_jpg_bp = Blueprint("heic_jpg", __name__, url_prefix="/convert")
@heic_jpg_bp.route("/heic-to-jpg", methods=["POST"])
def heic_to_jpg():
    return handle_conversion(
         allowed_extension=["heic"]
        ,convert_function= convert_heic_jpg
        ,output_extension="jpg"
        ,tool_name="heic_to_jpg"
    )