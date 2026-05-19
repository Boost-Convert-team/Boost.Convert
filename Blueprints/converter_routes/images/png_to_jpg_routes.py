from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.images.png_to_jpg_service import convert_png_jpg

png_jpg_bp = Blueprint("png_jpg", __name__, url_prefix="/convert")
@png_jpg_bp.route("/png-to-jpg", methods=["POST"])
def png_to_jpg():
    return handle_conversion(
         allowed_extension=["png"]
        ,convert_function= convert_png_jpg
        ,output_extension="jpg"
        ,tool_name="png_to_jpg"
    )