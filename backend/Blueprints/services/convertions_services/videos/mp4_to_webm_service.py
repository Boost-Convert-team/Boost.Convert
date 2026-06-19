from Blueprints.services.convertions_services.conversion_option_values import get_vp9_crf
from Blueprints.services.convertions_services.ffmpeg_runner import run_ffmpeg


def convert_mp4_webm(input_path, output_path, options=None):
    run_ffmpeg([
        "-i", input_path
        ,"-map", "0:v?"
        ,"-map", "0:a?"
        ,"-c:v", "libvpx-vp9"
        ,"-crf", str(get_vp9_crf(options or {}))
        ,"-b:v", "0"
        ,"-c:a", "libopus"
        ,"-map_metadata", "0"
        ,output_path
    ])
