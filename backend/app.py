from pathlib import Path

from flask import Flask, send_from_directory
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

    @app.context_processor
    def inject_global_template_data():
        favicon_path = Path(app.static_folder) / "img" / "logo boost.png"
        css_path = Path(app.static_folder) / "css"
        js_path = Path(app.static_folder) / "js"
        css_version = 0
        js_version = 0
        if css_path.exists():
            css_version = int(max(path.stat().st_mtime for path in css_path.rglob("*.css")))
        if js_path.exists():
            js_version = int(max(path.stat().st_mtime for path in js_path.rglob("*.js")))
        return {
            "favicon_version": int(favicon_path.stat().st_mtime) if favicon_path.exists() else 0,
            "css_version": css_version,
            "js_version": js_version,
            "tool_search_index": build_tool_search_index(),
            "tool_counts": build_tool_counts(),
        }

    @app.before_request
    def cleanup_conversion_files(): run_conversion_file_cleanup(app)

    @app.get("/favicon.ico")
    def favicon():
        response = send_from_directory(
            app.static_folder,
            "img/logo boost.png",
            mimetype="image/png",
            max_age=0,
        )
        response.cache_control.no_cache = True
        response.cache_control.no_store = True
        return response

    @app.get("/google8d88adeac885fa39.html")
    def google_search_console_verification():
        project_root = Path(__file__).resolve().parent.parent
        return send_from_directory(project_root, "google8d88adeac885fa39.html")

    registrando_blueprints(app)
    register_error_handlers(app)
    return app
