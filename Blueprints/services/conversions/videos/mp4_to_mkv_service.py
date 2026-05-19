import ffmpeg
from Blueprints.services.conversions.conversion_option_values import get_h264_crf, get_h264_preset
from Blueprints.services.conversions.ffmpeg_runner import get_ffmpeg_command

def convert_mp4_mkv(input_path, output_path, options=None):
    options = options or {}

    (
        ffmpeg.input(input_path)
        .output(output_path, vcodec="libx264", acodec="aac", crf=get_h264_crf(options), preset=get_h264_preset())
        .run(cmd=get_ffmpeg_command(), overwrite_output=True)
    )
