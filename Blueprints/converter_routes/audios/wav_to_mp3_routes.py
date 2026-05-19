from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.audios.wav_to_mp3_service import convert_wav_mp3

wav_mp3_bp = Blueprint("wav_mp3", __name__, url_prefix="/convert")
@wav_mp3_bp.route("/wav-to-mp3", methods=["POST"])
def wav_to_mp3():
    return handle_conversion(
         allowed_extension=["wav"]
        ,convert_function= convert_wav_mp3
        ,output_extension="mp3"
        ,tool_name="wav_to_mp3"
    )