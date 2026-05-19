from Blueprints.services.conversions.ffmpeg_runner import run_ffmpeg

def convert_wav_flac(input_path, output_path):
    run_ffmpeg(["-i", input_path, "-c:a", "flac", output_path])
