import os

def get_audio_bitrate(options): return options.get("audio_bitrate", "320k")

def get_sample_rate(options):
    sample_rate = options.get("sample_rate", "original")
    if sample_rate == "original": return None
    return int(sample_rate)

def get_image_quality(options): return int(options.get("image_quality", "95"))

def get_gif_fps(options):
    gif_fps = options.get("gif_fps", "original")
    if gif_fps == "original": return None
    return int(gif_fps)

def get_gif_width(options):
    gif_width = options.get("gif_width", "original")
    if gif_width == "original": return None
    return int(gif_width)

def get_gif_duration(options):
    gif_duration = options.get("gif_duration", "original")
    if gif_duration == "original": return None
    return int(gif_duration)

def get_h264_crf(options):
    values = {"smaller": 30, "balanced": 20, "high": 16}
    return values.get(options.get("video_quality", "high"), 16)

def get_h264_preset(): return os.getenv("VIDEO_FFMPEG_PRESET", "veryfast")

def get_vp9_crf(options):
    values = {"smaller": 38, "balanced": 30, "high": 24}
    return values.get(options.get("video_quality", "high"), 24)

def get_pdf_render_zoom():
    try: return max(1.0, float(os.getenv("PDF_RENDER_ZOOM", "2.0")))
    except ValueError: return 2.0
