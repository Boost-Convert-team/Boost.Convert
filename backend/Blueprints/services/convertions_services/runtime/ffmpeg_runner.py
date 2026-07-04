import os
import shutil
import subprocess
from functools import lru_cache
from os import PathLike
from typing import Sequence, Union


FFmpegArgument = Union[str, PathLike[str]]


@lru_cache(maxsize=1)
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
    subprocess.run(
        [get_ffmpeg_command(), "-y", *arguments],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
        timeout=get_conversion_timeout_seconds(),
    )


def get_conversion_timeout_seconds() -> int:
    """Return the subprocess timeout used by media conversions.

    Example: timeout = get_conversion_timeout_seconds()
    """
    try:
        return max(1, int(os.getenv("CONVERSION_TIMEOUT_SECONDS", "300")))
    except ValueError:
        return 300


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
