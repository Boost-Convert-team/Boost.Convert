from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.videos.webm_to_mp4_service import convert_webm_mp4

webm_mp4_bp = Blueprint("webm_mp4", __name__)
@webm_mp4_bp.route("/convert/webm-to-mp4", methods=["POST"])
def webm_to_mp4():
    return handle_conversion(
         allowed_extension=["webm"]
        ,convert_function=convert_webm_mp4
        ,output_extension="mp4"
        ,tool_name="webm_to_mp4"
    )