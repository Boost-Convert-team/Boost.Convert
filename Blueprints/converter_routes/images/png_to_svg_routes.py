from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.images.png_to_svg_service import convert_png_svg

png_svg_bp = Blueprint("png_svg", __name__, url_prefix="/convert")
@png_svg_bp.route("/png-to-svg", methods=["POST"])
def png_to_svg():
    return handle_conversion(
         allowed_extension=["png"]
        ,convert_function= convert_png_svg
        ,output_extension="svg"
        ,tool_name="png_to_svg"
    )