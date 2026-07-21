from Blueprints.services.convertions_services.conversion_rules.conversion_option_values import (
    get_vp9_crf,
)
from Blueprints.services.convertions_services.runtime.ffmpeg_runner import run_ffmpeg


DEFAULT_WEBM_QUALITY = "balanced"
VP9_CPU_USED_BY_QUALITY = {"smaller": "5", "balanced": "4", "high": "3"}


def convert_mp4_webm(input_path, output_path, options=None):
    options = _normalize_webm_options(options or {})
    run_ffmpeg([
        "-i", input_path
        ,"-map", "0:v?"
        ,"-map", "0:a?"
        ,"-c:v", "libvpx-vp9"
        ,"-crf", str(get_vp9_crf(options or {}))
        ,"-b:v", "0"
        ,"-deadline", "good"
        ,"-cpu-used", _get_vp9_cpu_used(options)
        ,"-row-mt", "1"
        ,"-threads", "0"
        ,"-c:a", "libopus"
        ,"-b:a", "128k"
        ,"-map_metadata", "0"
        ,output_path
    ])


def _normalize_webm_options(options):
    normalized = dict(options or {})
    normalized.setdefault("video_quality", DEFAULT_WEBM_QUALITY)
    if normalized["video_quality"] not in VP9_CPU_USED_BY_QUALITY: normalized["video_quality"] = DEFAULT_WEBM_QUALITY
    return normalized


def _get_vp9_cpu_used(options):
    return VP9_CPU_USED_BY_QUALITY.get(options.get("video_quality", DEFAULT_WEBM_QUALITY), "4")
