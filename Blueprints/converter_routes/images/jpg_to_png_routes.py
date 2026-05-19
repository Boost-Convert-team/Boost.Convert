from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.images.jpg_to_png_service import convert_jpg_png

jpg_png_bp = Blueprint("jpg_png", __name__, url_prefix="/convert")
@jpg_png_bp.route("/jpg-to-png", methods=["POST"])
def jpg_to_png():
    return handle_conversion(
         allowed_extension=["jpg"]
        ,convert_function= convert_jpg_png
        ,output_extension="png"
        ,tool_name="jpg_to_png"
    )