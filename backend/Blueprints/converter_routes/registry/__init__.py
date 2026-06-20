from Blueprints.converter_routes.registry.audio import AUDIO_CONVERTER_ROUTES
from Blueprints.converter_routes.registry.documents import DOCUMENT_CONVERTER_ROUTES
from Blueprints.converter_routes.registry.images import IMAGE_CONVERTER_ROUTES
from Blueprints.converter_routes.registry.videos import VIDEO_CONVERTER_ROUTES


SIMPLE_CONVERTER_ROUTES = (
    *AUDIO_CONVERTER_ROUTES,
    *DOCUMENT_CONVERTER_ROUTES,
    *IMAGE_CONVERTER_ROUTES,
    *VIDEO_CONVERTER_ROUTES,
)
