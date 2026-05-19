from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.videos.mp4_to_mp3_service import convert_mp4_mp3

mp4_mp3_bp = Blueprint("mp4_mp3", __name__, url_prefix="/convert")
@mp4_mp3_bp.route("/mp4-to-mp3", methods=["POST"])
def mp4_to_mp3():
    return handle_conversion(
         allowed_extension=["mp4"]
        ,convert_function= convert_mp4_mp3
        ,output_extension="mp3"
        ,tool_name="mp4_to_mp3"
    )