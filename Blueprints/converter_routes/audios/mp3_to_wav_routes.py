from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.audios.mp3_to_wav_service import convert_mp3_wav

mp3_wav_bp = Blueprint("mp3_wav", __name__, url_prefix="/convert")
@mp3_wav_bp.route("/mp3-to-wav", methods=["POST"])
def mp3_to_wav():
    return handle_conversion(
         allowed_extension=["mp3"]
        ,convert_function= convert_mp3_wav
        ,output_extension="wav"
        ,tool_name="mp3_to_wav"
    )