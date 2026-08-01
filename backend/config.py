import os
import secrets
from datetime import timedelta
from pathlib import Path

from sqlalchemy.engine import URL


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE_URI = f"sqlite:///{(BASE_DIR / 'instance' / 'boost_converter_dev.sqlite').as_posix()}"


def normalize_database_uri(uri):
    uri = uri.strip()
    if uri.startswith("postgres://"):
        return f"postgresql+psycopg://{uri.removeprefix('postgres://')}"
    if uri.startswith("postgresql://"):
        return f"postgresql+psycopg://{uri.removeprefix('postgresql://')}"

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


def build_postgres_uri_from_env():
    host = os.getenv("POSTGRES_HOST") or os.getenv("PGHOST")
    database = os.getenv("POSTGRES_DB") or os.getenv("PGDATABASE")
    username = os.getenv("POSTGRES_USER") or os.getenv("PGUSER")
    password = os.getenv("POSTGRES_PASSWORD") or os.getenv("PGPASSWORD")

    if not all([host, database, username, password]):
        return None

    query = {}
    sslmode = os.getenv("POSTGRES_SSLMODE") or os.getenv("PGSSLMODE")
    if sslmode:
        query["sslmode"] = sslmode

    url = URL.create(
        "postgresql+psycopg",
        username=username,
        password=password,
        host=host,
        port=int(os.getenv("POSTGRES_PORT") or os.getenv("PGPORT") or "5432"),
        database=database,
        query=query,
    )
    return url.render_as_string(hide_password=False)


def get_database_uri():
    configured_uri = (
        os.getenv("DATABASE_URL")
        or os.getenv("SQLALCHEMY_DATABASE_URI")
        or build_postgres_uri_from_env()
    )
    return normalize_database_uri(configured_uri) if configured_uri else DEFAULT_DATABASE_URI


def get_sqlalchemy_engine_options(database_uri):
    if database_uri.startswith("postgresql"):
        return {"pool_pre_ping": True}
    return {}


def get_bool_env(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int_env(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def get_secret_key():
    secret_key = os.getenv("SECRET_KEY")
    environment = get_app_environment()
    if secret_key:
        if is_weak_secret_key(secret_key):
            raise RuntimeError("SECRET_KEY insegura: valor fraco; esperado segredo aleatorio com pelo menos 32 caracteres.")
        return secret_key
    if environment in {"production", "prod"}:
        raise RuntimeError("SECRET_KEY precisa ser configurado em producao.")
    return secrets.token_urlsafe(32)


def get_app_environment():
    return (os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or "development").lower()


def is_production_environment():
    return get_app_environment() in {"production", "prod"}


def is_weak_secret_key(secret_key):
    weak_values = {"dev", "development", "secret", "change-me", "changeme", "boost"}
    return len(secret_key.strip()) < 32 or secret_key.strip().lower() in weak_values


class Config:
    APP_ENV = get_app_environment()
    SECRET_KEY = get_secret_key()
    SQLALCHEMY_DATABASE_URI = get_database_uri()
    SQLALCHEMY_ENGINE_OPTIONS = get_sqlalchemy_engine_options(SQLALCHEMY_DATABASE_URI)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "2048")) * 1024 * 1024
    FORCE_HTTPS = get_bool_env("FORCE_HTTPS", is_production_environment())
    PREFERRED_URL_SCHEME = "https" if FORCE_HTTPS else "http"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = get_bool_env("SESSION_COOKIE_SECURE", FORCE_HTTPS)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=get_int_env("SESSION_LIFETIME_MINUTES", 120))
    SESSION_PERMANENT = get_bool_env("SESSION_PERMANENT", True)
    TRUST_PROXY_HEADERS = get_bool_env("TRUST_PROXY_HEADERS", is_production_environment())
    CSRF_ENABLED = get_bool_env("CSRF_ENABLED", True)
    RATE_LIMIT_ENABLED = get_bool_env("RATE_LIMIT_ENABLED", True)
    HSTS_MAX_AGE_SECONDS = get_int_env("HSTS_MAX_AGE_SECONDS", 31536000)
    MERCADO_PAGO_ACCESS_TOKEN = os.getenv("MERCADO_PAGO_ACCESS_TOKEN")
    MERCADO_PAGO_PUBLIC_KEY = os.getenv("MERCADO_PAGO_PUBLIC_KEY")
    MERCADO_PAGO_WEBHOOK_SECRET = os.getenv("MERCADO_PAGO_WEBHOOK_SECRET")
    MERCADO_PAGO_COLLECTOR_ID = os.getenv("MERCADO_PAGO_COLLECTOR_ID")
    MERCADO_PAGO_ENVIRONMENT = (os.getenv("MERCADO_PAGO_ENVIRONMENT") or "").lower()
    MERCADO_PAGO_PLAN_PRICE = os.getenv("MERCADO_PAGO_PLAN_PRICE", "19.90")
    MERCADO_PAGO_MAX_INSTALLMENTS = get_int_env("MERCADO_PAGO_MAX_INSTALLMENTS", 12)
    MERCADO_PAGO_WEBHOOK_TOLERANCE_SECONDS = get_int_env(
        "MERCADO_PAGO_WEBHOOK_TOLERANCE_SECONDS", 300
    )
    MERCADO_PAGO_RECONCILE_INTERVAL_SECONDS = get_int_env(
        "MERCADO_PAGO_RECONCILE_INTERVAL_SECONDS", 10
    )
    # Public SEO origin.  This must not depend on the inbound Host or proxy
    # scheme because those values may vary behind nginx and during health
    # checks.  All canonicals, Open Graph URLs and sitemap entries use it.
    BASE_URL = (os.getenv("BASE_URL") or "https://boostconvert.com.br").rstrip("/")
    SEND_FILE_MAX_AGE_DEFAULT = timedelta(days=365)
    CONVERSION_FILE_RETENTION_MINUTES = get_int_env("CONVERSION_FILE_RETENTION_MINUTES", 15)
    AI_TRANSCRIPT_RETENTION_MINUTES = get_int_env("AI_TRANSCRIPT_RETENTION_MINUTES", 15)
    CONVERSION_CLEANUP_INTERVAL_MINUTES = get_int_env("CONVERSION_CLEANUP_INTERVAL_MINUTES", 5)
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.getenv(
        "GOOGLE_REDIRECT_URI",
        "http://localhost:5001/login/google/callback",
    )


def should_auto_create_db(app):
    if os.getenv("AUTO_CREATE_DB") == "1": return True
    if os.getenv("AUTO_CREATE_DB") == "0": return False
    return False


def validate_mercado_pago_config(app):
    """Fail closed for a production payment configuration."""
    environment = str(app.config.get("MERCADO_PAGO_ENVIRONMENT") or "").lower()
    access_token = str(app.config.get("MERCADO_PAGO_ACCESS_TOKEN") or "").strip()
    public_key = str(app.config.get("MERCADO_PAGO_PUBLIC_KEY") or "").strip()
    if (
        not environment
        and app.config.get("APP_ENV") not in {"production", "prod"}
        and access_token.startswith("TEST-")
        and public_key.startswith("TEST-")
    ):
        environment = "test"
        app.config["MERCADO_PAGO_ENVIRONMENT"] = environment
    if environment not in {"test", "production"}:
        message = "MERCADO_PAGO_ENVIRONMENT deve ser test ou production."
        if app.config.get("APP_ENV") in {"production", "prod"}:
            raise RuntimeError(message)
        app.logger.warning("mercado_pago_config_incomplete field=environment")
        return

    required = {
        "MERCADO_PAGO_ACCESS_TOKEN": app.config.get("MERCADO_PAGO_ACCESS_TOKEN"),
        "MERCADO_PAGO_PUBLIC_KEY": app.config.get("MERCADO_PAGO_PUBLIC_KEY"),
        "MERCADO_PAGO_WEBHOOK_SECRET": app.config.get("MERCADO_PAGO_WEBHOOK_SECRET"),
        "MERCADO_PAGO_COLLECTOR_ID": app.config.get("MERCADO_PAGO_COLLECTOR_ID"),
    }
    missing = sorted(name for name, value in required.items() if not str(value or "").strip())
    is_production_app = app.config.get("APP_ENV") in {"production", "prod"}
    if missing and is_production_app:
        raise RuntimeError(
            "Configuracao Mercado Pago ausente: " + ", ".join(missing)
        )
    if missing:
        app.logger.warning(
            "mercado_pago_config_incomplete fields=%s", ",".join(missing)
        )
        return

    access_token = str(required["MERCADO_PAGO_ACCESS_TOKEN"])
    public_key = str(required["MERCADO_PAGO_PUBLIC_KEY"])
    uses_test_credentials = access_token.startswith("TEST-") or public_key.startswith("TEST-")
    if environment == "production" and uses_test_credentials:
        raise RuntimeError("Credenciais TEST nao podem ser usadas no ambiente Mercado Pago production.")
    if environment == "test" and not (
        access_token.startswith("TEST-") and public_key.startswith("TEST-")
    ):
        raise RuntimeError("Ambiente Mercado Pago test exige credenciais TEST.")
    if is_production_app and environment != "production":
        raise RuntimeError("Aplicacao em producao exige MERCADO_PAGO_ENVIRONMENT=production.")
    if not is_production_app and environment == "production":
        raise RuntimeError("Pagamentos reais sao bloqueados fora da aplicacao em producao.")
    if is_production_app and not str(app.config.get("BASE_URL") or "").startswith("https://"):
        raise RuntimeError("BASE_URL HTTPS e obrigatoria para pagamentos em producao.")
