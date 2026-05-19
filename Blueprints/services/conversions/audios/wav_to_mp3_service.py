from Blueprints.services.conversions.conversion_option_values import get_audio_bitrate
from Blueprints.services.conversions.ffmpeg_runner import run_ffmpeg

def convert_wav_mp3(input_path, output_path, options=None):
    options = options or {}
    run_ffmpeg(["-i", input_path, "-vn", "-c:a", "libmp3lame", "-b:a", get_audio_bitrate(options), output_path])
