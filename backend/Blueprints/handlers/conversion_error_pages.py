from flask import render_template, url_for
from flask.typing import ResponseReturnValue

from Blueprints.services.convertions_services.errors.conversion_errors import build_friendly_conversion_error


def render_conversion_error_response(error: BaseException, status_code: int) -> ResponseReturnValue:
    """Renders a Boost-styled conversion error page.

    Example: render_conversion_error_response(ValueError("Nenhum arquivo enviado"), 400)
    """
    friendly_error = build_friendly_conversion_error(error)
    return render_template(
        "conversion_error.html",
        error_title=friendly_error.title,
        error_message=friendly_error.message,
        error_recovery=friendly_error.recovery,
        action_url=url_for("home.tools"),
    ), status_code
