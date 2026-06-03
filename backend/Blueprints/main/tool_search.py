import re

from flask import url_for

from Blueprints.main.tools_registry import TOOLS


FORMAT_ALIASES = {
    "aac": "audio som musica",
    "avi": "video filme",
    "csv": "excel planilha tabela dados",
    "doc": "word documento texto doc antigo",
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
    "odp": "libreoffice impress apresentacao slide",
    "ods": "libreoffice calc planilha tabela",
    "odt": "libreoffice writer documento texto",
    "mp3": "audio som musica",
    "mp4": "video filme",
    "ogg": "audio som musica",
    "pdf": "documento arquivo",
    "png": "imagem foto",
    "ppt": "powerpoint apresentacao slide antigo",
    "pptx": "powerpoint apresentacao slide ppt",
    "svg": "vetor imagem icone",
    "txt": "texto text documento",
    "wav": "audio som musica",
    "webm": "video web",
    "webp": "imagem foto web",
    "wma": "audio som musica",
    "xls": "excel planilha tabela antigo",
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
            slug = route.removeprefix("/convert/").strip("/")
            label = format_tool_search_label(tool["name"])
            formats = re.findall(r"[a-z0-9]+", slug)
            aliases = build_tool_aliases(label, slug, category, formats)
            if tool.get("aliases"):
                aliases = f"{aliases} {tool['aliases']}"

            entries.append(
                {
                    "label": label,
                    "category": format_search_category(category),
                    "url": tool.get("page_route") or url_for("home.converter_tool", slug=slug),
                    "icon": tool.get("icon") or get_tool_search_icon(category, slug),
                    "aliases": aliases,
                }
            )

    entries.extend(
        [
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
        ]
    )

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

    add_special_tool_aliases(slug, aliases)
    return " ".join(sorted(aliases))


def add_special_tool_aliases(slug, aliases):
    special_aliases = {
        "pdf-to-docx": "pdf para word pdf word converter pdf word transformar pdf em word pdf em doc",
        "docx-to-pdf": "word para pdf word pdf doc para pdf",
        "pdf-to-xlsx": "pdf para excel pdf excel pdf planilha",
        "xlsx-to-pdf": "excel para pdf planilha para pdf",
        "pptx-to-pdf": "powerpoint para pdf ppt para pdf slide para pdf",
        "ppt-to-pptx": "ppt antigo para pptx powerpoint atualizar apresentacao",
        "ppt-to-pdf": "ppt antigo para pdf powerpoint para pdf",
        "doc-to-docx": "doc antigo para docx word atualizar documento",
        "doc-to-pdf": "doc antigo para pdf word para pdf",
        "xls-to-xlsx": "xls antigo para xlsx excel atualizar planilha",
        "xls-to-pdf": "xls antigo para pdf excel para pdf planilha",
        "pdf-compress": "comprimir pdf compactar pdf reduzir pdf diminuir tamanho pdf",
        "pdf-merge": "juntar pdf unir pdf combinar pdf mesclar pdf",
        "pdf-split": "dividir pdf separar pdf cortar pdf extrair paginas",
        "pdf-rotate": "rotacionar pdf girar pdf virar paginas",
        "pdf-protect": "proteger pdf senha pdf bloquear pdf criptografar pdf",
        "pdf-unlock": "desbloquear pdf remover senha pdf destravar pdf",
        "pdf-extract-images": "extrair imagens do pdf salvar fotos do pdf",
        "pdf-ocr-searchable": "ocr pdf pesquisavel pdf escaneado texto pesquisavel",
    }
    if slug in special_aliases:
        aliases.add(special_aliases[slug])
