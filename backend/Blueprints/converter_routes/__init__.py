from Blueprints.converter_routes.documents.files_to_zip_routes import files_zip_bp
from Blueprints.converter_routes.documents.pdf_merge_routes import pdf_merge_bp
from Blueprints.converter_routes.images.images_to_pdf_routes import images_pdf_bp
from Blueprints.converter_routes.registry import SIMPLE_CONVERTER_ROUTES
from Blueprints.converter_routes.route_factory import create_simple_converter_blueprint


_SIMPLE_BLUEPRINTS_BY_NAME = {
    route.blueprint_name: create_simple_converter_blueprint(route)
    for route in SIMPLE_CONVERTER_ROUTES
}

for _blueprint_name, _blueprint in _SIMPLE_BLUEPRINTS_BY_NAME.items():
    globals()[f"{_blueprint_name}_bp"] = _blueprint

del _blueprint_name, _blueprint

__all__ = [
    *(f"{route.blueprint_name}_bp" for route in SIMPLE_CONVERTER_ROUTES),
    "pdf_merge_bp",
    "files_zip_bp",
    "images_pdf_bp",
]
