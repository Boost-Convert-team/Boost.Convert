from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.videos.mp4_to_mov_service import convert_mp4_mov

mp4_mov_bp = Blueprint("mp4_mov", __name__, url_prefix="/convert")
@mp4_mov_bp.route("/mp4-to-mov", methods=["POST"])
def mp4_to_mov():
    return handle_conversion(
         allowed_extension=["mp4"]
        ,convert_function= convert_mp4_mov
        ,output_extension="mov"
        ,tool_name="mp4_to_mov"
    )