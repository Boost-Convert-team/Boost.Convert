from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.videos.mkv_to_mp4_service import convert_mkv_mp4

mkv_mp4_bp = Blueprint("mkv_mp4", __name__, url_prefix="/convert")
@mkv_mp4_bp.route("/mkv-to-mp4", methods=["POST"])
def mkv_to_mp4():
    return handle_conversion(
         allowed_extension=["mkv"]
        ,convert_function= convert_mkv_mp4
        ,output_extension="mp4"
        ,tool_name="mkv_to_mp4"
    )
