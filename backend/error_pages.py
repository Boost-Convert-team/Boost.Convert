from flask import Flask, jsonify, request
from flask.typing import ResponseReturnValue
from werkzeug.exceptions import HTTPException

from Blueprints.handlers.conversion_error_pages import render_conversion_error_response


HTTP_ERROR_MESSAGES: dict[int, str] = {
    400: "Requisicao invalida.",
    403: "Acesso nao permitido.",
    404: "Pagina nao encontrada.",
    429: "Muitas requisicoes. Tente novamente em instantes.",
    413: "Arquivo maior que o limite geral.",
    500: "Erro interno do Boost.",
}


def register_error_handlers(app: Flask) -> None:
    """Registers Boost-styled HTTP error pages.

    Example: register_error_handlers(app)
    """
    for status_code in HTTP_ERROR_MESSAGES:
        app.register_error_handler(status_code, _handle_http_error)


def _handle_http_error(error: HTTPException) -> ResponseReturnValue:
    status_code = error.code or 500
    message = _get_http_error_message(status_code)
    if _wants_json_error():
        return jsonify({"ok": False, "error": message}), status_code
    return render_conversion_error_response(ValueError(message), status_code)


def _get_http_error_message(status_code: int) -> str:
    fallback_message = HTTP_ERROR_MESSAGES[500]
    if status_code in HTTP_ERROR_MESSAGES:
        return HTTP_ERROR_MESSAGES[status_code]
    return fallback_message


def _wants_json_error() -> bool:
    best_match = request.accept_mimetypes.best_match(["application/json", "text/html"])
    is_api_request = request.path.startswith("/api/")
    accepts_json_first = best_match == "application/json"
    return is_api_request or accepts_json_first
