from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.audios.ogg_to_wav_service import convert_ogg_wav

ogg_wav_bp = Blueprint("ogg_wav", __name__, url_prefix="/convert")
@ogg_wav_bp.route("/ogg-to-wav", methods=["POST"])
def ogg_to_wav():
    return handle_conversion(
         allowed_extension=["ogg"]
        ,convert_function= convert_ogg_wav
        ,output_extension="wav"
        ,tool_name="ogg_to_wav"
    )