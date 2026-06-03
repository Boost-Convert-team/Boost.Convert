from Blueprints.services.convertions_services.images.heic_to_jpg_service import convert_heic_jpg
from Blueprints.services.convertions_services.images.heic_to_png_service import convert_heic_png
from Blueprints.services.convertions_services.images.jpg_to_png_service import convert_jpg_png
from Blueprints.services.convertions_services.images.jpg_to_svg_service import convert_jpg_svg
from Blueprints.services.convertions_services.images.jpg_to_webp_service import convert_jpg_webp
from Blueprints.services.convertions_services.images.png_to_jpg_service import convert_png_jpg
from Blueprints.services.convertions_services.images.png_to_svg_service import convert_png_svg
from Blueprints.services.convertions_services.images.png_to_webp_service import convert_png_webp
from Blueprints.services.convertions_services.images.svg_to_jpg_service import convert_svg_jpg
from Blueprints.services.convertions_services.images.svg_to_png_service import convert_svg_png
from Blueprints.services.convertions_services.images.webp_to_jpg_service import convert_webp_jpg
from Blueprints.services.convertions_services.images.webp_to_png_service import convert_webp_png

from Blueprints.converter_routes.registry.models import SimpleConverterRoute


IMAGE_CONVERTER_ROUTES = (
    # Images
    SimpleConverterRoute("heic_jpg", "/convert/heic-to-jpg", ("heic",), convert_heic_jpg, "jpg", "heic_to_jpg"),
    SimpleConverterRoute("heic_png", "/convert/heic-to-png", ("heic",), convert_heic_png, "png", "heic_to_png"),
    SimpleConverterRoute("jpg_png", "/convert/jpg-to-png", ("jpg", "jpeg"), convert_jpg_png, "png", "jpg_to_png"),
    SimpleConverterRoute("jpg_svg", "/convert/jpg-to-svg", ("jpg", "jpeg"), convert_jpg_svg, "svg", "jpg_to_svg"),
    SimpleConverterRoute("jpg_webp", "/convert/jpg-to-webp", ("jpg", "jpeg"), convert_jpg_webp, "webp", "jpg_to_webp"),
    SimpleConverterRoute("png_jpg", "/convert/png-to-jpg", ("png",), convert_png_jpg, "jpg", "png_to_jpg"),
    SimpleConverterRoute("png_svg", "/convert/png-to-svg", ("png",), convert_png_svg, "svg", "png_to_svg"),
    SimpleConverterRoute("png_webp", "/convert/png-to-webp", ("png",), convert_png_webp, "webp", "png_to_webp"),
    SimpleConverterRoute("svg_jpg", "/convert/svg-to-jpg", ("svg",), convert_svg_jpg, "jpg", "svg_to_jpg"),
    SimpleConverterRoute("svg_png", "/convert/svg-to-png", ("svg",), convert_svg_png, "png", "svg_to_png"),
    SimpleConverterRoute("webp_jpg", "/convert/webp-to-jpg", ("webp",), convert_webp_jpg, "jpg", "webp_to_jpg"),
    SimpleConverterRoute("webp_png", "/convert/webp-to-png", ("webp",), convert_webp_png, "png", "webp_to_png"),
)
