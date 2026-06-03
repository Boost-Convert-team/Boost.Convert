import os

def configure_media_dependencies():
    ffmpeg_path = find_python_ffmpeg()

    if not ffmpeg_path: return

    os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path
    add_to_path(os.path.dirname(ffmpeg_path))
    
def find_python_ffmpeg():
    try:
        import imageio_ffmpeg
    except ImportError:
        return None
    
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None
    
def add_to_path(directory):
    if not directory: return

    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    if directory not in path_entries: os.environ["PATH"] = directory + os.pathsep + os.environ.get("PATH", "")
