from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.images.png_to_webp_service import convert_png_webp

png_webp_bp = Blueprint("png_webp", __name__, url_prefix="/convert")
@png_webp_bp.route("/png-to-webp", methods=["POST"])
def png_to_webp():
    return handle_conversion(
         allowed_extension=["png"]
        ,convert_function= convert_png_webp
        ,output_extension="webp"
        ,tool_name="png_to_webp"
    )
