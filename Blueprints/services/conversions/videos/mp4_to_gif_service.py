import ffmpeg
from Blueprints.services.conversions.conversion_option_values import get_gif_fps, get_gif_width
from Blueprints.services.conversions.ffmpeg_runner import get_ffmpeg_command

def convert_mp4_gif(input_path, output_path, options=None):
    options = options or {}
    video = ffmpeg.input(input_path)

    gif_filters = f"fps={get_gif_fps(options)},scale={get_gif_width(options)}:-1"

    output = video.output(output_path,vf=gif_filters)
    output.run(cmd=get_ffmpeg_command(), overwrite_output=True)
