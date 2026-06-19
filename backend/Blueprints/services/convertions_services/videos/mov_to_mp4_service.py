from Blueprints.services.convertions_services.videos.video_preservation import convert_video_container_preserving_streams


def convert_mov_mp4(input_path, output_path, options=None):
    convert_video_container_preserving_streams(input_path, output_path, options or {})
