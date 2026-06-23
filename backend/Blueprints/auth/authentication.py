from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import login_user, logout_user
from extensions import db, oauth
from models import Usuario
from Blueprints.auth.passwords import hash_password, needs_password_rehash, verify_password

auth_bp = Blueprint("auth", __name__)
EMAIL_FIELD = "nomeForm"
PASSWORD_FIELD = "senhaForm"
INVALID_LOGIN_MESSAGE = "Usuario ou senha invalidos."

def normalize_email(email): return (email or "").strip().lower()
def get_auth_form_data(): return normalize_email(request.form.get(EMAIL_FIELD)), request.form.get(PASSWORD_FIELD, "")
def flash_and_redirect(message, endpoint):
    flash(message)
    return redirect(url_for(endpoint))
def validate_local_credentials(email, password, redirect_endpoint):
    if not email or not password: return flash_and_redirect("Preencha email e senha para continuar.", redirect_endpoint)
    return None
def validate_login_credentials(email, password):
    if not email or not password: return flash_and_redirect(INVALID_LOGIN_MESSAGE, "auth.login")
    return None
def start_authenticated_session(user):
    session.clear()
    session.permanent = True
    login_user(user)
def create_local_user(email, password):
    user = Usuario(email=email, senha=hash_password(password))
    db.session.add(user)
    db.session.commit()
    return user
def authenticate_local_user(email, password):
    user = db.session.query(Usuario).filter_by(email=email).first()
    if user is None or not verify_password(user.senha, password):
        return None
    if needs_password_rehash(user.senha):
        user.senha = hash_password(password)
        db.session.commit()
    return user
def get_or_create_google_user(user_info):
    google_id = user_info.get("sub")
    email = normalize_email(user_info.get("email"))
    nome = user_info.get("name")
    if not google_id or not email: return None
    user = Usuario.query.filter_by(google_id=google_id).first()
    if user: return user
    user = Usuario.query.filter_by(email=email).first()
    if user:
        user.google_id = google_id
        user.nome = user.nome or nome
    else:
        user = Usuario(email=email, nome=nome, google_id=google_id)
        db.session.add(user)
    db.session.commit()
    return user
def get_google_user_info(token):
    user_info = token.get("userinfo")
    if user_info: return user_info
    return oauth.google.userinfo()

@auth_bp.route("/registrar", methods=["GET", "POST"])
@auth_bp.route("/cadastro", methods=["GET", "POST"])
def registrar():
    if request.method == "GET": return render_template("registrar.html")
    email, password = get_auth_form_data()
    invalid_response = validate_local_credentials(email, password, "auth.registrar")
    if invalid_response: return invalid_response
    if Usuario.query.filter_by(email=email).first(): return flash_and_redirect("Nao foi possivel concluir o cadastro com estes dados.", "auth.registrar")
    user = create_local_user(email, password)
    start_authenticated_session(user)
    return redirect(url_for("home.conta"))

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET": return render_template("login.html")
    email, password = get_auth_form_data()
    invalid_response = validate_login_credentials(email, password)
    if invalid_response: return invalid_response
    user = authenticate_local_user(email, password)
    if not user: return flash_and_redirect(INVALID_LOGIN_MESSAGE, "auth.login")
    start_authenticated_session(user)
    return redirect(url_for("home.conta"))

@auth_bp.route("/logout")
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("home.home"))

@auth_bp.route("/login/google")
def google_login():
    if oauth is None: return flash_and_redirect("Login Google indisponivel.", "auth.login")
    redirect_uri = current_app.config["GOOGLE_REDIRECT_URI"]
    return oauth.google.authorize_redirect(redirect_uri)

@auth_bp.route("/login/google/callback")
def google_callback():
    if oauth is None: return flash_and_redirect("Login Google indisponivel.", "auth.login")
    try:
        token = oauth.google.authorize_access_token()
        user = get_or_create_google_user(get_google_user_info(token))
    except Exception as error:
        db.session.rollback()
        current_app.logger.warning("Falha no callback do login Google: %s", error)
        return flash_and_redirect("Nao foi possivel entrar com Google. Tente novamente.", "auth.login")
    if not user: return flash_and_redirect("Nao foi possivel entrar com Google.", "auth.login")
    start_authenticated_session(user)
    return redirect(url_for("home.conta"))
