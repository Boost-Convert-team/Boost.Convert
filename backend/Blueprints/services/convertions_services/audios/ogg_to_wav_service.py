from Blueprints.services.convertions_services.conversion_option_values import get_sample_rate
from Blueprints.services.convertions_services.ffmpeg_runner import run_ffmpeg


def convert_ogg_wav(input_path, output_path, options=None):
    args = [
        "-i", input_path
        ,"-vn"
    ]
    sample_rate = get_sample_rate(options or {})

    if sample_rate:
        args.extend(["-ar", str(sample_rate)])

    args.extend([
        "-c:a", "pcm_s16le"
        ,output_path
    ])
    run_ffmpeg(args)
