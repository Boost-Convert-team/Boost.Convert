import os
from collections.abc import Mapping
from os import PathLike
from typing import Union

from Blueprints.services.convertions_services.conversion_rules.conversion_option_values import (
    get_h264_crf,
    get_h264_preset,
)
from Blueprints.services.convertions_services.runtime.ffmpeg_runner import (
    FFmpegArgument,
    run_ffmpeg_with_fallback,
)


VideoPath = Union[str, PathLike[str]]


def convert_video_container_preserving_streams(
    input_path: VideoPath,
    output_path: VideoPath,
    options: Mapping[str, str] | None = None,
) -> None:
    """Change video container without re-encoding when FFmpeg accepts it.

    Example: convert_video_container_preserving_streams("input.mkv", "output.mp4")
    """
    option_values = options or {}
    run_ffmpeg_with_fallback(
        _build_stream_copy_arguments(input_path, output_path),
        _build_h264_aac_fallback_arguments(input_path, output_path, option_values),
    )


def _build_stream_copy_arguments(input_path: VideoPath, output_path: VideoPath) -> list[FFmpegArgument]:
    arguments: list[FFmpegArgument] = ["-i", input_path, "-map", "0", "-c", "copy", "-map_metadata", "0"]
    arguments.extend(_build_faststart_arguments(output_path))
    arguments.append(output_path)
    return arguments


def _build_h264_aac_fallback_arguments(
    input_path: VideoPath,
    output_path: VideoPath,
    options: Mapping[str, str],
) -> list[FFmpegArgument]:
    arguments: list[FFmpegArgument] = ["-i", input_path, "-map", "0:v?", "-map", "0:a?"]
    arguments.extend(["-c:v", "libx264", "-preset", get_h264_preset(), "-crf", str(get_h264_crf(options))])
    arguments.extend(["-c:a", "aac", "-map_metadata", "0"])
    arguments.extend(_build_faststart_arguments(output_path))
    arguments.append(output_path)
    return arguments


def _build_faststart_arguments(output_path: VideoPath) -> list[str]:
    extension = os.path.splitext(os.fspath(output_path))[1].lower()
    if extension not in {".mp4", ".mov"}:
        return []
    return ["-movflags", "+faststart"]
