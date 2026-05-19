from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.audios.flac_to_wav_service import convert_flac_wav

flac_wav_bp = Blueprint("flac_wav", __name__, url_prefix="/convert")
@flac_wav_bp.route("/flac-to-wav", methods=["POST"])
def flac_to_wav():
    return handle_conversion(
         allowed_extension=["flac"]
        ,convert_function= convert_flac_wav
        ,output_extension="wav"
        ,tool_name="flac_to_wav"
    )