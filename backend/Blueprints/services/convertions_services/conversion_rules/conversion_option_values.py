import os


def get_audio_bitrate(options) -> str:
    return options.get("audio_bitrate", "320k")


def get_sample_rate(options) -> int | None:
    sample_rate = options.get("sample_rate", "original")
    if sample_rate == "original":
        return None
    return int(sample_rate)


def get_image_quality(options) -> int:
    return int(options.get("image_quality", "95"))


def get_gif_fps(options) -> int | None:
    gif_fps = options.get("gif_fps", "original")
    if gif_fps == "original":
        return None
    return int(gif_fps)


def get_gif_width(options) -> int | None:
    gif_width = options.get("gif_width", "original")
    if gif_width == "original":
        return None
    return int(gif_width)


def get_gif_duration(options) -> int | None:
    gif_duration = options.get("gif_duration", "original")
    if gif_duration == "original":
        return None
    return int(gif_duration)


def get_h264_crf(options) -> int:
    values = {"smaller": 30, "balanced": 20, "high": 16}
    return values.get(options.get("video_quality", "high"), 16)


def get_h264_preset() -> str:
    return os.getenv("VIDEO_FFMPEG_PRESET", "veryfast")


def get_vp9_crf(options) -> int:
    values = {"smaller": 38, "balanced": 30, "high": 24}
    return values.get(options.get("video_quality", "high"), 24)


def get_pdf_render_zoom() -> float:
    try:
        return max(1.0, float(os.getenv("PDF_RENDER_ZOOM", "2.0")))
    except ValueError:
        return 2.0
