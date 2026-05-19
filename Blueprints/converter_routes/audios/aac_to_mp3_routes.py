from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.audios.aac_to_mp3_service import convert_aac_mp3

aac_mp3_bp = Blueprint("aac_mp3", __name__, url_prefix="/convert")
@aac_mp3_bp.route("/aac-to-mp3", methods=["POST"])
def aac_to_mp3():
    return handle_conversion(
         allowed_extension=["aac"]
        ,convert_function= convert_aac_mp3
        ,output_extension="mp3"
        ,tool_name="aac_to_mp3"
    )