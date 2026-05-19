from dataclasses import dataclass

from flask import request
from flask_login import current_user

from Blueprints.services.conversions.conversion_options import sanitize_conversion_options
from Blueprints.services.subscription.access_service import can_use_tool
from Blueprints.services.subscription.session_service import get_anonymous_session_id

@dataclass
class ConversionRequestContext:
    usuario: object
    session_id: str
    usage: object
    options: dict

def get_conversion_request_context():
    usuario = current_user if current_user.is_authenticated else None
    session_id = None if usuario is not None else get_anonymous_session_id()

    allowed, message, usage = can_use_tool(usuario=usuario, session_id=session_id)

    if not allowed:
        raise PermissionError(message)

    return ConversionRequestContext(
        usuario=usuario,
        session_id=session_id,
        usage=usage,
        options=sanitize_conversion_options(request.path, request.form),
    )

def get_uploaded_files():
    files = request.files.getlist("files") or request.files.getlist("file")
    return [file for file in files if file and file.filename]
