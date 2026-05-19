from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.videos.mp4_to_mkv_service import convert_mp4_mkv

mp4_mkv_bp = Blueprint("mp4_mkv", __name__, url_prefix="/convert")
@mp4_mkv_bp.route("/mp4-to-mkv", methods=["POST"])
def mp4_to_mkv():
    return handle_conversion(
         allowed_extension=["mp4"]
        ,convert_function= convert_mp4_mkv
        ,output_extension="mkv"
        ,tool_name="mp4_to_mkv"
    )