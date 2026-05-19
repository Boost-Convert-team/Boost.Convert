import ffmpeg
from Blueprints.services.conversions.conversion_option_values import get_vp9_crf
from Blueprints.services.conversions.ffmpeg_runner import get_ffmpeg_command


def convert_mp4_webm(input_path, output_path, options=None):
    options = options or {}

    (
        ffmpeg.input(input_path)
        .output(
            output_path,
            vcodec="libvpx-vp9",
            acodec="libopus",
            **{"crf": get_vp9_crf(options), "b:v": "0"},
        )
        .run(cmd=get_ffmpeg_command(), overwrite_output=True)
    )
