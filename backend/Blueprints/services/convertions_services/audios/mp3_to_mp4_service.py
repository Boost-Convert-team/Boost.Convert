from Blueprints.services.convertions_services.conversion_option_values import get_audio_bitrate, get_h264_preset
from Blueprints.services.convertions_services.ffmpeg_runner import run_ffmpeg


def convert_mp3_mp4(input_path, output_path, options=None):
    run_ffmpeg([
        "-f", "lavfi"
        ,"-i", "color=c=black:s=1280x720:r=30"
        ,"-i", input_path
        ,"-shortest"
        ,"-c:v", "libx264"
        ,"-preset", get_h264_preset()
        ,"-c:a", "aac"
        ,"-b:a", get_audio_bitrate(options or {})
        ,output_path
    ])
