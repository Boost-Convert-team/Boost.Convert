from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.videos.mov_to_mp4_service import convert_mov_mp4

mov_mp4_bp = Blueprint("mov_mp4", __name__, url_prefix="/convert")
@mov_mp4_bp.route("/mov-to-mp4", methods=["POST"])
def mov_to_mp4():
    return handle_conversion(
         allowed_extension=["mov"]
        ,convert_function= convert_mov_mp4
        ,output_extension="mp4"
        ,tool_name="mov_to_mp4"
    )
