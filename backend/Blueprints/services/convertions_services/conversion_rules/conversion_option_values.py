import os

def get_audio_bitrate(options): return options.get("audio_bitrate", "192k")

def get_sample_rate(options):
    sample_rate = options.get("sample_rate", "original")
    if sample_rate == "original": return None
    return int(sample_rate)

def get_image_quality(options): return int(options.get("image_quality", "85"))

def get_gif_fps(options): return int(options.get("gif_fps", "10"))

def get_gif_width(options): return int(options.get("gif_width", "480"))

def get_h264_crf(options):
    values = {"smaller": 30, "balanced": 23, "high": 18}
    return values.get(options.get("video_quality", "balanced"), 23)

def get_h264_preset(): return os.getenv("VIDEO_FFMPEG_PRESET", "veryfast")

def get_vp9_crf(options):
    values = {"smaller": 38, "balanced": 33, "high": 28}
    return values.get(options.get("video_quality", "balanced"), 33)

def get_pdf_render_zoom():
    try: return max(1.0, float(os.getenv("PDF_RENDER_ZOOM", "1.5")))
    except ValueError: return 1.5
