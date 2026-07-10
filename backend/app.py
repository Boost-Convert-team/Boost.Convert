from pathlib import Path
from functools import lru_cache

from flask import Flask, request, send_from_directory
from dotenv import load_dotenv

load_dotenv()

from flask_migrate import Migrate
import pip_system_certs.wrapt_requests
from config import Config
from error_pages import register_error_handlers
from extensions import db, lm, oauth
from models import Usuario
from register_blueprints import registrando_blueprints
from security import init_security
from Blueprints.main.tool_search import build_tool_search_index
from Blueprints.main.tools_registry import build_tool_counts
from Blueprints.main.seo_helpers import public_url, robots_for_path
from Blueprints.services.convertions_services.file_cleanup import run_conversion_file_cleanup
from Blueprints.services.convertions_services.media_dependencies import configure_media_dependencies

migrate = Migrate()

def create_app():
    configure_media_dependencies()

    app = Flask(
        __name__,
        template_folder="../frontend/templates",
        static_folder="../frontend/static",
    )
    app.config.from_object(Config)
    app.secret_key = app.config["SECRET_KEY"]

    db.init_app(app)
    migrate.init_app(app, db)
    lm.init_app(app)
    init_security(app)

    if oauth is not None:
        oauth.init_app(app)
        oauth.register(
            name="google",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

    @lm.user_loader
    def user_loader(id):
        return db.session.get(Usuario, int(id))

    @lru_cache(maxsize=1)
    def get_cached_tool_search_index():
        return build_tool_search_index()

    @lru_cache(maxsize=1)
    def get_asset_versions():
        favicon_path = Path(app.static_folder) / "img" / "favicon-192.png"
        css_path = Path(app.static_folder) / "css"
        js_path = Path(app.static_folder) / "js"
        css_version = int(max(path.stat().st_mtime for path in css_path.rglob("*.css"))) if css_path.exists() else 0
        js_version = int(max(path.stat().st_mtime for path in js_path.rglob("*.js"))) if js_path.exists() else 0
        return {
            "favicon_version": int(favicon_path.stat().st_mtime) if favicon_path.exists() else 0,
            "css_version": css_version,
            "js_version": js_version,
        }

    @app.context_processor
    def inject_global_template_data():
        asset_versions = get_asset_versions()
        return {
            **asset_versions,
            "tool_search_index": get_cached_tool_search_index(),
            "tool_counts": build_tool_counts(),
            "default_canonical_url": public_url(request.path),
            "default_og_image_url": public_url("/static/img/boost-convert-logo-clean.png"),
            "default_robots": robots_for_path(request.path),
        }

    @app.before_request
    def cleanup_conversion_files(): run_conversion_file_cleanup(app)

    @app.get("/favicon.ico")
    def favicon():
        response = send_from_directory(
            app.static_folder,
            "img/favicon-192.png",
            mimetype="image/png",
            max_age=86400,
        )
        return response

    @app.get("/google8d88adeac885fa39.html")
    def google_search_console_verification():
        project_root = Path(__file__).resolve().parent.parent
        return send_from_directory(project_root, "google8d88adeac885fa39.html")

    registrando_blueprints(app)
    register_error_handlers(app)
    return app
