import shutil
import subprocess

def get_ffmpeg_command():
    try:
        import imageio_ffmpeg
    except ImportError:
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path: return ffmpeg_path
        raise RuntimeError("FFmpeg nao encontrado. Instale imageio-ffmpeg ou adicione ffmpeg ao PATH.")
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path: return ffmpeg_path
        raise RuntimeError("FFmpeg nao encontrado. Instale imageio-ffmpeg ou adicione ffmpeg ao PATH.")

def run_ffmpeg(arguments):
    subprocess.run([get_ffmpeg_command(), "-y", *arguments], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
