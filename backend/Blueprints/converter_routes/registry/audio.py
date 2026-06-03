from Blueprints.services.convertions_services.audios.aac_to_mp3_service import convert_aac_mp3
from Blueprints.services.convertions_services.audios.flac_to_mp3_service import convert_flac_mp3
from Blueprints.services.convertions_services.audios.flac_to_wav_service import convert_flac_wav
from Blueprints.services.convertions_services.audios.mp3_to_mp4_service import convert_mp3_mp4
from Blueprints.services.convertions_services.audios.mp3_to_wav_service import convert_mp3_wav
from Blueprints.services.convertions_services.audios.ogg_to_mp3_service import convert_ogg_mp3
from Blueprints.services.convertions_services.audios.ogg_to_wav_service import convert_ogg_wav
from Blueprints.services.convertions_services.audios.wav_to_flac_service import convert_wav_flac
from Blueprints.services.convertions_services.audios.wav_to_mp3_service import convert_wav_mp3
from Blueprints.services.convertions_services.audios.wma_to_mp3_service import convert_wma_mp3

from Blueprints.converter_routes.registry.models import SimpleConverterRoute


AUDIO_CONVERTER_ROUTES = (
    # Audios
    SimpleConverterRoute("aac_mp3", "/convert/aac-to-mp3", ("aac",), convert_aac_mp3, "mp3", "aac_to_mp3"),
    SimpleConverterRoute("flac_mp3", "/convert/flac-to-mp3", ("flac",), convert_flac_mp3, "mp3", "flac_to_mp3"),
    SimpleConverterRoute("flac_wav", "/convert/flac-to-wav", ("flac",), convert_flac_wav, "wav", "flac_to_wav"),
    SimpleConverterRoute("mp3_mp4", "/convert/mp3-to-mp4", ("mp3",), convert_mp3_mp4, "mp4", "mp3_to_mp4"),
    SimpleConverterRoute("mp3_wav", "/convert/mp3-to-wav", ("mp3",), convert_mp3_wav, "wav", "mp3_to_wav"),
    SimpleConverterRoute("ogg_mp3", "/convert/ogg-to-mp3", ("ogg",), convert_ogg_mp3, "mp3", "ogg_to_mp3"),
    SimpleConverterRoute("ogg_wav", "/convert/ogg-to-wav", ("ogg",), convert_ogg_wav, "wav", "ogg_to_wav"),
    SimpleConverterRoute("wav_flac", "/convert/wav-to-flac", ("wav",), convert_wav_flac, "flac", "wav_to_flac"),
    SimpleConverterRoute("wav_mp3", "/convert/wav-to-mp3", ("wav",), convert_wav_mp3, "mp3", "wav_to_mp3"),
    SimpleConverterRoute("wma_mp3", "/convert/wma-to-mp3", ("wma",), convert_wma_mp3, "mp3", "wma_to_mp3"),
)
