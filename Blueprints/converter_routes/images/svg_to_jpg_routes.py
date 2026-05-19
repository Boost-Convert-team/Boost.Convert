from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.images.svg_to_jpg_service import convert_svg_jpg

svg_jpg_bp = Blueprint("svg_jpg", __name__, url_prefix="/convert")
@svg_jpg_bp.route("/svg-to-jpg", methods=["POST"])
def svg_to_jpg():
    return handle_conversion(
         allowed_extension=["svg"]
        ,convert_function= convert_svg_jpg
        ,output_extension="jpg"
        ,tool_name="svg_to_jpg"
    )