from Blueprints.services.convertions_services.conversion_rules.conversion_option_values import (
    get_audio_bitrate,
)
from Blueprints.services.convertions_services.runtime.ffmpeg_runner import run_ffmpeg_with_fallback


def convert_mp3_mp4(input_path, output_path, options=None):
    run_ffmpeg_with_fallback(
        ["-i", input_path, "-vn", "-c:a", "copy", "-map_metadata", "0", output_path],
        ["-i", input_path, "-vn", "-c:a", "aac", "-b:a", get_audio_bitrate(options or {}), "-map_metadata", "0", output_path],
    )
