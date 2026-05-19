from Blueprints.services.conversions.conversion_option_values import get_sample_rate
from Blueprints.services.conversions.ffmpeg_runner import run_ffmpeg

def convert_ogg_wav(input_path, output_path, options=None):
    options = options or {}
    arguments = ["-i", input_path]
    sample_rate = get_sample_rate(options)

    if sample_rate is not None:
        arguments.extend(["-ar", str(sample_rate)])

    run_ffmpeg([*arguments, "-f", "wav", output_path])
