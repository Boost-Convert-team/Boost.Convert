from Blueprints.services.convertions_services.videos.avi_to_mp4_service import convert_avi_mp4
from Blueprints.services.convertions_services.videos.mkv_to_mp4_service import convert_mkv_mp4
from Blueprints.services.convertions_services.videos.mov_to_mp4_service import convert_mov_mp4
from Blueprints.services.convertions_services.videos.mp4_to_gif_service import convert_mp4_gif
from Blueprints.services.convertions_services.videos.mp4_to_mkv_service import convert_mp4_mkv
from Blueprints.services.convertions_services.videos.mp4_to_mov_service import convert_mp4_mov
from Blueprints.services.convertions_services.videos.mp4_to_mp3_service import convert_mp4_mp3
from Blueprints.services.convertions_services.videos.mp4_to_wav_service import convert_mp4_wav
from Blueprints.services.convertions_services.videos.mp4_to_webm_service import convert_mp4_webm
from Blueprints.services.convertions_services.videos.webm_to_mp4_service import convert_webm_mp4

from Blueprints.converter_routes.registry.models import SimpleConverterRoute


VIDEO_CONVERTER_ROUTES = (
    # Videos
    SimpleConverterRoute("avi_mp4", "/convert/avi-to-mp4", ("avi",), convert_avi_mp4, "mp4", "avi_to_mp4"),
    SimpleConverterRoute("mkv_mp4", "/convert/mkv-to-mp4", ("mkv",), convert_mkv_mp4, "mp4", "mkv_to_mp4"),
    SimpleConverterRoute("mov_mp4", "/convert/mov-to-mp4", ("mov",), convert_mov_mp4, "mp4", "mov_to_mp4"),
    SimpleConverterRoute("mp4_gif", "/convert/mp4-to-gif", ("mp4",), convert_mp4_gif, "gif", "mp4_to_gif"),
    SimpleConverterRoute("mp4_mkv", "/convert/mp4-to-mkv", ("mp4",), convert_mp4_mkv, "mkv", "mp4_to_mkv"),
    SimpleConverterRoute("mp4_mov", "/convert/mp4-to-mov", ("mp4",), convert_mp4_mov, "mov", "mp4_to_mov"),
    SimpleConverterRoute("mp4_mp3", "/convert/mp4-to-mp3", ("mp4",), convert_mp4_mp3, "mp3", "mp4_to_mp3"),
    SimpleConverterRoute("mp4_wav", "/convert/mp4-to-wav", ("mp4",), convert_mp4_wav, "wav", "mp4_to_wav"),
    SimpleConverterRoute("mp4_webm", "/convert/mp4-to-webm", ("mp4",), convert_mp4_webm, "webm", "mp4_to_webm"),
    SimpleConverterRoute("webm_mp4", "/convert/webm-to-mp4", ("webm",), convert_webm_mp4, "mp4", "webm_to_mp4"),
)
