from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.audios.flac_to_mp3_service import convert_flac_mp3

flac_mp3_bp = Blueprint("flac_mp3", __name__, url_prefix="/convert")
@flac_mp3_bp.route("/flac-to-mp3", methods=["POST"])
def flac_to_mp3():
    return handle_conversion(
         allowed_extension=["flac"]
        ,convert_function= convert_flac_mp3
        ,output_extension="mp3"
        ,tool_name="flac_to_mp3"
    )