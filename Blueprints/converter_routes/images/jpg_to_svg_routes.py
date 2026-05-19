from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.images.jpg_to_svg_service import convert_jpg_svg

jpg_svg_bp = Blueprint("jpg_svg", __name__, url_prefix="/convert")
@jpg_svg_bp.route("/jpg-to-svg", methods=["POST"])
def jpg_to_svg():
    return handle_conversion(
         allowed_extension=["jpg"]
        ,convert_function= convert_jpg_svg
        ,output_extension="svg"
        ,tool_name="jpg_to_svg"
    )