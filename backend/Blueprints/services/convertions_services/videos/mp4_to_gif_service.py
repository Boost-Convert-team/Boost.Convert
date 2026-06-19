from Blueprints.services.convertions_services.conversion_option_values import get_gif_fps, get_gif_width
from Blueprints.services.convertions_services.ffmpeg_runner import run_ffmpeg


def convert_mp4_gif(input_path, output_path, options=None):
    filter_chain = _build_gif_filter_chain(options or {})
    run_ffmpeg([
        "-i", input_path
        ,"-filter_complex", f"[0:v]{filter_chain},split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
        ,output_path
    ])


def _build_gif_filter_chain(options):
    filters = []
    if get_gif_fps(options): filters.append(f"fps={get_gif_fps(options)}")
    if get_gif_width(options): filters.append(f"scale={get_gif_width(options)}:-1")
    return ",".join(filters) if filters else "null"
