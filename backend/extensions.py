from flask_login import LoginManager
from db import db

try:
    from authlib.integrations.flask_client import OAuth
except ImportError:
    OAuth = None

lm = LoginManager()
lm.login_view = 'auth.login'

oauth = OAuth() if OAuth is not None else None
