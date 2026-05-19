from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.audios.ogg_to_mp3_service import convert_ogg_mp3

ogg_mp3_bp = Blueprint("ogg_mp3", __name__, url_prefix="/convert")
@ogg_mp3_bp.route("/ogg-to-mp3", methods=["POST"])
def ogg_to_mp3():
    return handle_conversion(
         allowed_extension=["ogg"]
        ,convert_function= convert_ogg_mp3
        ,output_extension="mp3"
        ,tool_name="ogg_to_mp3"
    )