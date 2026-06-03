from Blueprints.services.convertions_services.ffmpeg_runner import run_ffmpeg


def convert_wav_flac(input_path, output_path, options=None):
    run_ffmpeg([
        "-i", input_path
        ,"-vn"
        ,"-c:a", "flac"
        ,output_path
    ])
