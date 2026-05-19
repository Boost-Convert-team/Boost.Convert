from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.audios.wma_to_mp3_service import convert_wma_mp3

wma_mp3_bp = Blueprint("wma_mp3", __name__, url_prefix="/convert")
@wma_mp3_bp.route("/wma-to-mp3", methods=["POST"])
def wma_to_mp3():
    return handle_conversion(
         allowed_extension=["wma"]
        ,convert_function= convert_wma_mp3
        ,output_extension="mp3"
        ,tool_name="wma_to_mp3"
    )