from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.images.svg_to_png_service import convert_svg_png

svg_png_bp = Blueprint("svg_png", __name__, url_prefix="/convert")
@svg_png_bp.route("/svg-to-png", methods=["POST"])
def svg_to_png():
    return handle_conversion(
         allowed_extension=["svg"]
        ,convert_function= convert_svg_png
        ,output_extension="png"
        ,tool_name="svg_to_png"
    )