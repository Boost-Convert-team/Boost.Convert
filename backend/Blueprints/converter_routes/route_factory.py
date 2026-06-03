from flask import Blueprint
from Blueprints.handlers.conversion_handlers import handle_conversion

def create_simple_converter_blueprint(route):
    blueprint = Blueprint(route.blueprint_name, __name__)
    blueprint.add_url_rule(
        route.url_rule,
        endpoint=route.endpoint,
        view_func=create_simple_converter_view(route),
        methods=["POST"],
    )
    return blueprint

def create_simple_converter_blueprints(routes): return [create_simple_converter_blueprint(route) for route in routes]

def create_simple_converter_view(route):
    def converter_view():
        return handle_conversion(
            allowed_extension=route.allowed_extensions,
            convert_function=route.convert_function,
            output_extension=route.output_extension,
            tool_name=route.tool_name,
        )

    converter_view.__name__ = route.endpoint
    return converter_view
