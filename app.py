from flask import Flask, url_for
from flask_migrate import Migrate
import pip_system_certs.wrapt_requests
from extensions import db, lm, oauth
from models import Usuario
from register_blueprints import registrando_blueprints
from Blueprints.main.tools_registry import TOOLS
from Blueprints.services.conversions.file_cleanup import run_conversion_file_cleanup
from Blueprints.services.conversions.media_dependencies import configure_media_dependencies
from dotenv import load_dotenv
import os
import re

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

    @app.context_processor
    def inject_tool_search_index():
        return {"tool_search_index": build_tool_search_index()}

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return "Arquivo muito grande para upload.", 413

    @app.before_request
    def cleanup_conversion_files():
        run_conversion_file_cleanup(app)

    registrando_blueprints(app)
    return app


FORMAT_ALIASES = {
    "aac": "audio som musica",
    "avi": "video filme",
    "csv": "excel planilha tabela dados",
    "docx": "word documento texto doc",
    "flac": "audio som musica",
    "gif": "video animacao imagem",
    "heic": "iphone foto imagem",
    "html": "site pagina web navegador",
    "jpeg": "jpg foto imagem",
    "jpg": "jpeg foto imagem",
    "json": "dados api tabela",
    "md": "markdown texto documento",
    "mkv": "video filme",
    "mov": "video iphone quicktime",
    "mp3": "audio som musica",
    "mp4": "video filme",
    "ogg": "audio som musica",
    "pdf": "documento arquivo",
    "png": "imagem foto",
    "pptx": "powerpoint apresentacao slide ppt",
    "svg": "vetor imagem icone",
    "txt": "texto text documento",
    "wav": "audio som musica",
    "webm": "video web",
    "webp": "imagem foto web",
    "wma": "audio som musica",
    "xlsx": "excel planilha tabela",
}

ACTION_ALIASES = {
    "compress": "comprimir compactar reduzir diminuir otimizar leve",
    "edit": "editar alterar modificar",
    "merge": "juntar unir combinar mesclar anexar",
    "split": "dividir separar cortar extrair paginas",
}


def build_tool_search_index():
    entries = []

    for category, tools in TOOLS.items():
        for tool in tools:
            route = tool["route"]
            slug = route.removeprefix("/convert/")
            label = format_tool_search_label(tool["name"])
            formats = re.findall(r"[a-z0-9]+", slug)
            aliases = build_tool_aliases(label, slug, category, formats)

            entries.append({
                "label": label,
                "category": format_search_category(category),
                "url": url_for("home.converter_tool", slug=slug),
                "icon": get_tool_search_icon(category, slug),
                "aliases": aliases,
            })

    entries.extend([
        {
            "label": "OCR PDF",
            "category": "OCR",
            "url": url_for("home.tools") + "#ocr",
            "icon": "scan-text",
            "aliases": "ocr reconhecer texto extrair texto pdf imagem scanner texto pesquisavel",
        },
        {
            "label": "OCR imagem",
            "category": "OCR",
            "url": url_for("home.tools") + "#ocr",
            "icon": "scan-line",
            "aliases": "ocr imagem foto reconhecer texto extrair texto scanner",
        },
        {
            "label": "AI Tools",
            "category": "AI",
            "url": url_for("home.tools") + "#ai-tools",
            "icon": "bot",
            "aliases": "ai ia inteligencia artificial automacao assistente ferramentas inteligentes",
        },
    ])

    return entries


def format_tool_search_label(name):
    return name.replace(" -> ", " para ")


def format_search_category(category):
    labels = {
        "Audios": "Audio",
        "Documentos": "PDF",
        "Imagens": "Imagem",
        "Videos": "Video",
    }
    return labels.get(category, category)


def get_tool_search_icon(category, slug):
    if "pdf" in slug:
        return "file-text"
    if category == "Imagens":
        return "image"
    if category == "Videos":
        return "play-circle"
    if category == "Audios":
        return "audio-lines"
    if "csv" in slug or "xlsx" in slug or "json" in slug:
        return "table"
    return "file"


def build_tool_aliases(label, slug, category, formats):
    aliases = {
        label,
        label.replace(" para ", " to "),
        label.replace(" para ", " converter para "),
        slug,
        slug.replace("-", " "),
        category,
        "converter conversor conversao transformar arquivo ferramenta",
    }

    for fmt in formats:
        aliases.add(fmt)
        if fmt in FORMAT_ALIASES:
            aliases.add(FORMAT_ALIASES[fmt])
        if fmt in ACTION_ALIASES:
            aliases.add(ACTION_ALIASES[fmt])

    if "-to-" in slug:
        source, target = slug.split("-to-", 1)
        source_aliases = FORMAT_ALIASES.get(source, "")
        target_aliases = FORMAT_ALIASES.get(target, "")
        aliases.add(f"{source} para {target}")
        aliases.add(f"{source} para {target_aliases}")
        aliases.add(f"{source_aliases} para {target}")
        aliases.add(f"{source_aliases} converter para {target_aliases}")
        if "video" in source_aliases and "audio" in target_aliases:
            aliases.add("video para audio video em audio extrair audio de video")

    if slug == "pdf-to-docx":
        aliases.add("pdf para word pdf word converter pdf word transformar pdf em word pdf em doc")
    if slug == "docx-to-pdf":
        aliases.add("word para pdf word pdf doc para pdf")
    if slug == "pdf-to-xlsx":
        aliases.add("pdf para excel pdf excel pdf planilha")
    if slug == "xlsx-to-pdf":
        aliases.add("excel para pdf planilha para pdf")
    if slug == "pptx-to-pdf":
        aliases.add("powerpoint para pdf ppt para pdf slide para pdf")
    if slug == "pdf-compress":
        aliases.add("comprimir pdf compactar pdf reduzir pdf diminuir tamanho pdf")
    if slug == "pdf-merge":
        aliases.add("juntar pdf unir pdf combinar pdf mesclar pdf")
    if slug == "pdf-split":
        aliases.add("dividir pdf separar pdf cortar pdf extrair paginas")

    return " ".join(sorted(aliases))
