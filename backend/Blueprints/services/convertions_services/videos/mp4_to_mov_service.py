from Blueprints.services.convertions_services.videos.video_preservation import convert_video_container_preserving_streams


def convert_mp4_mov(input_path, output_path, options=None):
    convert_video_container_preserving_streams(input_path, output_path, options or {})
