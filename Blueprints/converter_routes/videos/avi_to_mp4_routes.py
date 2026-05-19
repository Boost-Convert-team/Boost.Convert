from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.videos.avi_to_mp4_service import convert_avi_mp4

avi_mp4_bp = Blueprint("avi_mp4", __name__)
@avi_mp4_bp.route("/convert/avi-to-mp4", methods=["POST"])
def avi_to_mp4():
    return handle_conversion(
         allowed_extension=["avi"]
        ,convert_function=convert_avi_mp4
        ,output_extension="mp4"
        ,tool_name="avi_to_mp4"
    )