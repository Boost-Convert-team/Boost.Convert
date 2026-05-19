from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.videos.mp4_to_webm_service import convert_mp4_webm

mp4_webm_bp = Blueprint("mp4_webm", __name__, url_prefix="/convert")
@mp4_webm_bp.route("/mp4-to-webm", methods=["POST"])
def mp4_to_webm():
    return handle_conversion(
         allowed_extension=["mp4"]
        ,convert_function= convert_mp4_webm
        ,output_extension="webm"
        ,tool_name="mp4_to_webm"
    )