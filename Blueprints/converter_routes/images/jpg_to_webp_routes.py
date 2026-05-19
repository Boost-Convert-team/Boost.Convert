from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.images.jpg_to_webp_service import convert_jpg_webp

jpg_webp_bp = Blueprint("jpg_webp", __name__, url_prefix="/convert")
@jpg_webp_bp.route("/jpg-to-webp", methods=["POST"])
def jpg_to_webp():
    return handle_conversion(
         allowed_extension=["jpg"]
        ,convert_function= convert_jpg_webp
        ,output_extension="webp"
        ,tool_name="jpg_to_webp"
    )