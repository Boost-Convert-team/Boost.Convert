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
        return {
            "tool_search_index": build_tool_search_index(),
            "tool_counts": build_tool_counts(),
        }

    @app.before_request
    def cleanup_conversion_files(): run_conversion_file_cleanup(app)

    @app.get("/favicon.ico")
    def favicon():
        return send_from_directory(
            app.static_folder,
            "img/logo boost.png",
            mimetype="image/png",
        )

    registrando_blueprints(app)
    register_error_handlers(app)
    return app
