from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.audios.wav_to_flac_service import convert_wav_flac

wav_flac_bp = Blueprint("wav_flac", __name__, url_prefix="/convert")
@wav_flac_bp.route("/wav-to-flac", methods=["POST"])
def wav_to_flac():
    return handle_conversion(
         allowed_extension=["wav"]
        ,convert_function= convert_wav_flac
        ,output_extension="flac"
        ,tool_name="wav_to_flac"
    )