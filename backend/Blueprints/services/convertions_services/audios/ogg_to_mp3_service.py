from Blueprints.services.convertions_services.conversion_rules.conversion_option_values import (
    get_audio_bitrate,
)
from Blueprints.services.convertions_services.runtime.ffmpeg_runner import run_ffmpeg


def convert_ogg_mp3(input_path, output_path, options=None):
    run_ffmpeg([
        "-i", input_path
        ,"-vn"
        ,"-c:a", "libmp3lame"
        ,"-b:a", get_audio_bitrate(options or {})
        ,output_path
    ])
