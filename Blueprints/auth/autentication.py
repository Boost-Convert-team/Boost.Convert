import hashlib

from authlib.integrations.base_client.errors import MismatchingStateError, OAuthError
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from requests.exceptions import SSLError
from sqlalchemy.exc import IntegrityError

from extensions import db, oauth
from models import Usuario

auth_bp = Blueprint("auth", __name__)

EMAIL_FIELD = "nomeForm"
PASSWORD_FIELD = "senhaForm"


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def normalize_email(email):
    return (email or "").strip().lower()


def get_auth_form_data():
    return (
        normalize_email(request.form.get(EMAIL_FIELD)),
        request.form.get(PASSWORD_FIELD, ""),
    )


def redirect_home_if_authenticated():
    if current_user.is_authenticated:
        return redirect(url_for("home.home"))

    return None


def find_user_by_email(email):
    return db.session.query(Usuario).filter_by(email=email).first()


def find_user_by_google_id(google_id):
    return db.session.query(Usuario).filter_by(google_id=google_id).first()


def flash_and_redirect(message, endpoint):
    flash(message)
    return redirect(url_for(endpoint))


def validate_local_credentials(email, password, redirect_endpoint):
    if not email or not password:
        return flash_and_redirect("Preencha email e senha para continuar.", redirect_endpoint)

    return None


def create_local_user(email, password):
    user = Usuario(email=email, senha=hash_password(password))
    db.session.add(user)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None

    return user


def authenticate_local_user(email, password):
    password_hash = hash_password(password)
    return db.session.query(Usuario).filter_by(email=email, senha=password_hash).first()


def is_google_oauth_available():
    if oauth is None:
        return False, "Instale a dependencia Authlib para usar o login com Google."

    if not current_app.config.get("GOOGLE_CLIENT_ID") or not current_app.config.get("GOOGLE_CLIENT_SECRET"):
        return False, "Configure GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET para usar o login com Google."

    return True, None


def localhost_url_for(endpoint):
    port = request.host.split(":", 1)[1] if ":" in request.host else "5000"
    return f"http://localhost:{port}{url_for(endpoint)}"


def canonical_external_url(endpoint):
    external_url = url_for(endpoint, _external=True)

    if external_url.startswith("http://127.0.0.1:"):
        external_url = external_url.replace("http://127.0.0.1:", "http://localhost:", 1)

    return external_url


def get_google_redirect_uri():
    configured_uri = current_app.config.get("GOOGLE_REDIRECT_URI")

    if configured_uri:
        return configured_uri

    return canonical_external_url("auth.google_callback")


def get_google_user_info(token):
    user_info = token.get("userinfo")

    if user_info is None:
        user_info = oauth.google.get("userinfo").json()

    google_id = user_info.get("sub")
    email = normalize_email(user_info.get("email"))
    name = user_info.get("name")

    if not google_id or not email:
        return None

    return {
        "google_id": google_id,
        "email": email,
        "name": name,
    }


def upsert_google_user(profile):
    user = find_user_by_google_id(profile["google_id"])

    if user is not None:
        return user

    user = find_user_by_email(profile["email"])

    if user is None:
        user = Usuario(
            email=profile["email"],
            nome=profile["name"],
            google_id=profile["google_id"],
        )
        db.session.add(user)
    else:
        user.google_id = profile["google_id"]
        user.nome = user.nome or profile["name"]

    db.session.commit()
    return user


@auth_bp.route("/registrar", methods=["GET", "POST"])
def registrar():
    authenticated_redirect = redirect_home_if_authenticated()
    if authenticated_redirect:
        return authenticated_redirect

    if request.method == "GET":
        return render_template("registrar.html")

    email, password = get_auth_form_data()
    invalid_response = validate_local_credentials(email, password, "auth.registrar")
    if invalid_response:
        return invalid_response

    if find_user_by_email(email):
        return flash_and_redirect("Este email ja esta cadastrado. Faca login ou use outro email.", "auth.registrar")

    user = create_local_user(email, password)
    if user is None:
        return flash_and_redirect("Nao foi possivel criar sua conta agora. Tente novamente.", "auth.registrar")

    login_user(user)
    return redirect(url_for("home.home"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    return registrar()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    authenticated_redirect = redirect_home_if_authenticated()
    if authenticated_redirect:
        return authenticated_redirect

    if request.method == "GET":
        return render_template("login.html")

    email, password = get_auth_form_data()
    invalid_response = validate_local_credentials(email, password, "auth.login")
    if invalid_response:
        return invalid_response

    user = authenticate_local_user(email, password)

    if not user:
        return flash_and_redirect("Email ou senha incorretos. Tente novamente.", "auth.login")

    login_user(user)
    return redirect(url_for("home.home"))


@auth_bp.route("/login/google")
def google_login():
    authenticated_redirect = redirect_home_if_authenticated()
    if authenticated_redirect:
        return authenticated_redirect

    if request.host.startswith("127.0.0.1"):
        return redirect(localhost_url_for("auth.google_login"))

    available, error_message = is_google_oauth_available()
    if not available:
        return flash_and_redirect(error_message, "auth.login")

    return oauth.google.authorize_redirect(get_google_redirect_uri())


@auth_bp.route("/login/google/callback")
def google_callback():
    available, error_message = is_google_oauth_available()
    if not available:
        return flash_and_redirect(error_message, "auth.login")

    try:
        token = oauth.google.authorize_access_token()
        profile = get_google_user_info(token)

        if profile is None:
            return flash_and_redirect("Nao foi possivel obter os dados da sua conta Google.", "auth.login")

        user = upsert_google_user(profile)
    except MismatchingStateError:
        return flash_and_redirect("A sessao do login com Google expirou. Tente entrar novamente.", "auth.login")
    except OAuthError:
        return flash_and_redirect("Nao foi possivel concluir o login com Google. Tente novamente.", "auth.login")
    except SSLError:
        current_app.logger.exception("Erro SSL ao concluir login com Google")
        return flash_and_redirect("Erro SSL ao conectar com o Google. Reinicie o servidor e tente novamente.", "auth.login")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Erro inesperado ao concluir login com Google")
        return flash_and_redirect("Nao foi possivel concluir o login com Google agora. Tente novamente.", "auth.login")

    login_user(user)
    return redirect(url_for("home.home"))


@auth_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("home.home"))
