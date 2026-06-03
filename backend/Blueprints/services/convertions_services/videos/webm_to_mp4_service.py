from Blueprints.services.convertions_services.conversion_option_values import get_h264_crf, get_h264_preset
from Blueprints.services.convertions_services.ffmpeg_runner import run_ffmpeg


def convert_webm_mp4(input_path, output_path, options=None):
    run_ffmpeg([
        "-i", input_path
        ,"-c:v", "libx264"
        ,"-preset", get_h264_preset()
        ,"-crf", str(get_h264_crf(options or {}))
        ,"-c:a", "aac"
        ,output_path
    ])
