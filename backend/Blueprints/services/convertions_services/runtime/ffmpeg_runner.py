import shutil
import subprocess
from os import PathLike
from typing import Sequence, Union


FFmpegArgument = Union[str, PathLike[str]]


def get_ffmpeg_command() -> str:
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


def run_ffmpeg(arguments: Sequence[FFmpegArgument]) -> None:
    subprocess.run([get_ffmpeg_command(), "-y", *arguments], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def run_ffmpeg_with_fallback(
    primary_arguments: Sequence[FFmpegArgument],
    fallback_arguments: Sequence[FFmpegArgument],
) -> None:
    """Run a preserving FFmpeg command before falling back to conversion.

    Example: run_ffmpeg_with_fallback(["-i", "in.mkv", "-c", "copy", "out.mp4"], fallback)
    """
    try:
        run_ffmpeg(primary_arguments)
    except subprocess.CalledProcessError:
        run_ffmpeg(fallback_arguments)
