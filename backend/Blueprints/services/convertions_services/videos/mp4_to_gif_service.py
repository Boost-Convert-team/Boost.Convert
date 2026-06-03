from Blueprints.services.convertions_services.conversion_option_values import get_gif_fps, get_gif_width
from Blueprints.services.convertions_services.ffmpeg_runner import run_ffmpeg


def convert_mp4_gif(input_path, output_path, options=None):
    run_ffmpeg([
        "-i", input_path
        ,"-vf", f"fps={get_gif_fps(options or {})},scale={get_gif_width(options or {})}:-1"
        ,output_path
    ])
