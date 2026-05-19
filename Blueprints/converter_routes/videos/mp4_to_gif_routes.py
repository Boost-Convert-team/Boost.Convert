from flask import Blueprint
from Blueprints.handler_convertions import handle_conversion
from Blueprints.services.conversions.videos.mp4_to_gif_service import convert_mp4_gif

mp4_gif_bp = Blueprint("mp4_gif", __name__)
@mp4_gif_bp.route("/convert/mp4-to-gif", methods=["POST"])
def mp4_to_gif():
    return handle_conversion(
         allowed_extension=["mp4"]
        ,convert_function=convert_mp4_gif
        ,output_extension="gif"
        ,tool_name="mp4_to_gif"
    )