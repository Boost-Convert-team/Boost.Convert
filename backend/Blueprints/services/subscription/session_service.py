from flask import session
import uuid

def get_anonymous_session_id():
    if "anon_id" not in session: session["anon_id"] = str(uuid.uuid4())
    return session["anon_id"]
