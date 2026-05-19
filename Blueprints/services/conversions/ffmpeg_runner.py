import subprocess

def get_ffmpeg_command():
    try:
        import imageio_ffmpeg
    except ImportError:
        return "ffmpeg"

    return imageio_ffmpeg.get_ffmpeg_exe()

def run_ffmpeg(arguments):
    command = [get_ffmpeg_command(), "-y", *arguments]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
