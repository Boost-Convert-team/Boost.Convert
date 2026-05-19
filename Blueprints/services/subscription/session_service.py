import uuid
from flask import session


def get_anonymous_session_id():
    anonimo_id = session.get("anon_id")

    if anonimo_id is None:
        anonimo_id = str(uuid.uuid4())
        session["anon_id"] = anonimo_id

    return anonimo_id