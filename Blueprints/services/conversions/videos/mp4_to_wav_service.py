import ffmpeg
from Blueprints.services.conversions.conversion_option_values import get_sample_rate
from Blueprints.services.conversions.ffmpeg_runner import get_ffmpeg_command

def convert_mp4_wav(input_path, output_path, options=None):
    options = options or {}
    output_kwargs = {"format": "wav"}
    sample_rate = get_sample_rate(options)

    if sample_rate is not None:
        output_kwargs["ar"] = sample_rate

    (
        ffmpeg.input(input_path)
        .output(output_path, **output_kwargs)
        .run(cmd=get_ffmpeg_command(), overwrite_output=True)
    )
