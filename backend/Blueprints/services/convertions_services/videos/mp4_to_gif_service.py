from Blueprints.services.convertions_services.conversion_option_values import get_gif_duration, get_gif_fps, get_gif_width
from Blueprints.services.convertions_services.ffmpeg_runner import run_ffmpeg


DEFAULT_GIF_DURATION_SECONDS = 10
DEFAULT_GIF_FPS = 10
DEFAULT_GIF_WIDTH = 480


def convert_mp4_gif(input_path, output_path, options=None):
    options = options or {}
    filter_chain = _build_gif_filter_chain(options)
    duration = _get_gif_duration(options)
    input_arguments = []
    if duration: input_arguments.extend(["-t", str(duration)])

    run_ffmpeg([
        *input_arguments
        ,"-i", input_path
        ,"-an"
        ,"-filter_complex", f"[0:v]{filter_chain},split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5"
        ,"-loop", "0"
        ,output_path
    ])


def _build_gif_filter_chain(options):
    filters = []
    gif_fps = get_gif_fps(options)
    gif_width = get_gif_width(options)

    if gif_fps is None and "gif_fps" not in options: gif_fps = DEFAULT_GIF_FPS
    if gif_width is None and "gif_width" not in options: gif_width = DEFAULT_GIF_WIDTH

    if gif_fps: filters.append(f"fps={gif_fps}")
    if gif_width: filters.append(f"scale='min({gif_width},iw)':-2:flags=lanczos")
    return ",".join(filters) if filters else "null"


def _get_gif_duration(options):
    gif_duration = get_gif_duration(options)
    if gif_duration is None and "gif_duration" not in options: gif_duration = DEFAULT_GIF_DURATION_SECONDS
    return gif_duration
