from flask import Flask
from flask_migrate import Migrate
import pip_system_certs.wrapt_requests
from extensions import db, lm, oauth
from models import Usuario
from register_blueprints import registrando_blueprints
from Blueprints.services.conversions.file_cleanup import run_conversion_file_cleanup
from Blueprints.services.conversions.media_dependencies import configure_media_dependencies
from dotenv import load_dotenv
import os

load_dotenv()

migrate = Migrate()

def create_app():
    configure_media_dependencies()

    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "dev")
    app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql+psycopg://postgres:arthur15@localhost:5432/BoostConverter"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024
    app.config["GOOGLE_CLIENT_ID"] = os.getenv("GOOGLE_CLIENT_ID")
    app.config["GOOGLE_CLIENT_SECRET"] = os.getenv("GOOGLE_CLIENT_SECRET")
    app.config["GOOGLE_REDIRECT_URI"] = os.getenv(
        "GOOGLE_REDIRECT_URI",
        "http://localhost:5000/login/google/callback",
    )
    
    db.init_app(app)
    migrate.init_app(app, db)
    lm.init_app(app)

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
    def user_loader(id): return db.session.get(Usuario, int(id))

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return "Arquivo muito grande para upload.", 413

    @app.before_request
    def cleanup_conversion_files():
        run_conversion_file_cleanup(app)

    registrando_blueprints(app)
    return app
