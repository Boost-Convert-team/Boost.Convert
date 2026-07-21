from Blueprints.services.convertions_services.conversion_rules.conversion_option_values import (
    get_sample_rate,
)
from Blueprints.services.convertions_services.runtime.ffmpeg_runner import run_ffmpeg


def convert_mp4_wav(input_path, output_path, options=None):
    args = [
        "-i", input_path
        ,"-vn"
    ]
    sample_rate = get_sample_rate(options or {})

    if sample_rate:
        args.extend(["-ar", str(sample_rate)])

    args.extend([
        "-c:a", "pcm_s24le"
        ,output_path
    ])
    run_ffmpeg(args)
