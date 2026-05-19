import ffmpeg
from Blueprints.services.conversions.conversion_option_values import get_audio_bitrate
from Blueprints.services.conversions.ffmpeg_runner import get_ffmpeg_command

def convert_mp4_mp3(input_path, output_path, options=None):
    options = options or {}

    (
        ffmpeg.input(input_path)
        .output(output_path, vn=None, acodec="libmp3lame", audio_bitrate=get_audio_bitrate(options))
        .run(cmd=get_ffmpeg_command(), overwrite_output=True)
    )
