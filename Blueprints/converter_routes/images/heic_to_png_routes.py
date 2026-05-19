from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.images.heic_to_png_service import convert_heic_png

heic_png_bp = Blueprint("heic_png", __name__, url_prefix="/convert")
@heic_png_bp.route("/heic-to-png", methods=["POST"])
def heic_to_png():
    return handle_conversion(
         allowed_extension=["heic"]
        ,convert_function= convert_heic_png
        ,output_extension="png"
        ,tool_name="heic_to_png"
    )