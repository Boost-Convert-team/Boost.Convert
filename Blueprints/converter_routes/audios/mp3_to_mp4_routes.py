from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.audios.mp3_to_mp4_service import convert_mp3_mp4

mp3_mp4_bp = Blueprint("mp3_mp4", __name__, url_prefix="/convert")
@mp3_mp4_bp.route("/mp3-to-mp4", methods=["POST"])
def mp3_to_mp4():
    return handle_conversion(
         allowed_extension=["mp3"]
        ,convert_function= convert_mp3_mp4
        ,output_extension="mp4"
        ,tool_name="mp3_to_mp4"
    )