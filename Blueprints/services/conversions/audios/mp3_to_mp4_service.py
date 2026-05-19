from Blueprints.services.conversions.ffmpeg_runner import run_ffmpeg

def convert_mp3_mp4(input_path, output_path):
    run_ffmpeg([
        "-f", "lavfi",
        "-i", "color=c=black:s=1280x720:r=24",
        "-i", input_path,
        "-shortest",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        output_path,
    ])
