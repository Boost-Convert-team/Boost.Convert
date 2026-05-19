from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.videos.mp4_to_wav_service import convert_mp4_wav

mp4_wav_bp = Blueprint("mp4_wav", __name__, url_prefix="/convert")
@mp4_wav_bp.route("/mp4-to-wav", methods=["POST"])
def mp4_to_wav():
    return handle_conversion(
         allowed_extension=["mp4"]
        ,convert_function= convert_mp4_wav
        ,output_extension="wav"
        ,tool_name="mp4_to_wav"
    )