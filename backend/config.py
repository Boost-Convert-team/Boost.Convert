import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_URI = f"sqlite:///{(BASE_DIR / 'instance' / 'boost_converter_dev.sqlite').as_posix()}"


def normalize_database_uri(uri):
    sqlite_prefix = "sqlite:///"
    if uri == "sqlite:///:memory:" or not uri.startswith(sqlite_prefix):
        return uri

    path_text = uri.removeprefix(sqlite_prefix)
    if Path(path_text).is_absolute() or path_text.startswith(("/", "\\")):
        return uri

    db_path = Path(path_text)
    if len(db_path.parts) == 1:
        db_path = Path("instance") / db_path

    return f"sqlite:///{(BASE_DIR / db_path).as_posix()}"


def get_database_uri():
    configured_uri = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI")
    return normalize_database_uri(configured_uri) if configured_uri else DEFAULT_DATABASE_URI

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")
    SQLALCHEMY_DATABASE_URI = get_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "2048")) * 1024 * 1024
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.getenv(
        "GOOGLE_REDIRECT_URI",
        "http://localhost:5000/login/google/callback",
    )


def should_auto_create_db(app):
    if os.getenv("AUTO_CREATE_DB") == "1": return True
    if os.getenv("AUTO_CREATE_DB") == "0": return False
    return False
