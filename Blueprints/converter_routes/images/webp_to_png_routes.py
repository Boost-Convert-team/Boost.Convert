from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.images.webp_to_png_service import convert_webp_png

webp_png_bp = Blueprint("webp_png", __name__, url_prefix="/convert")
@webp_png_bp.route("/webp-to-png", methods=["POST"])
def webp_to_png():
    return handle_conversion(
         allowed_extension=["webp"]
        ,convert_function= convert_webp_png
        ,output_extension="png"
        ,tool_name="webp_to_png"
    )