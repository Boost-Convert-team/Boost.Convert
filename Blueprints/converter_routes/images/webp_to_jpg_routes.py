from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.images.webp_to_jpg_service import convert_webp_jpg

webp_jpg_bp = Blueprint("webp_jpg", __name__, url_prefix="/convert")
@webp_jpg_bp.route("/webp-to-jpg", methods=["POST"])
def webp_to_jpg():
    return handle_conversion(
         allowed_extension=["webp"]
        ,convert_function= convert_webp_jpg
        ,output_extension="jpg"
        ,tool_name="webp_to_jpg"
    )