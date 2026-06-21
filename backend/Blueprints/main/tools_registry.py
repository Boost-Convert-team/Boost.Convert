TOOLS = {
    "Audios": [
        {"name": "AAC -> MP3", "route": "/convert/aac-to-mp3", "accept": ".aac"},
        {"name": "FLAC -> MP3", "route": "/convert/flac-to-mp3", "accept": ".flac"},
        {"name": "FLAC -> WAV", "route": "/convert/flac-to-wav", "accept": ".flac"},
        {"name": "MP3 -> MP4", "route": "/convert/mp3-to-mp4", "accept": ".mp3"},
        {"name": "MP3 -> WAV", "route": "/convert/mp3-to-wav", "accept": ".mp3"},
        {"name": "OGG -> MP3", "route": "/convert/ogg-to-mp3", "accept": ".ogg"},
        {"name": "OGG -> WAV", "route": "/convert/ogg-to-wav", "accept": ".ogg"},
        {"name": "WAV -> FLAC", "route": "/convert/wav-to-flac", "accept": ".wav"},
        {"name": "WAV -> MP3", "route": "/convert/wav-to-mp3", "accept": ".wav"},
        {"name": "WMA -> MP3", "route": "/convert/wma-to-mp3", "accept": ".wma"},
    ],
    "Documentos": [
        {"name": "Juntar PDF", "route": "/convert/pdf-merge", "accept": ".pdf", "multiple": True},
        {"name": "Dividir PDF", "route": "/convert/pdf-split", "accept": ".pdf"},
        {"name": "Comprimir PDF", "route": "/convert/pdf-compress", "accept": ".pdf"},
        {"name": "Rotacionar PDF", "route": "/convert/pdf-rotate", "accept": ".pdf", "aliases": "girar pdf virar pdf rotacionar paginas"},
        {"name": "Proteger PDF", "route": "/convert/pdf-protect", "accept": ".pdf", "aliases": "senha pdf criptografar pdf bloquear pdf"},
        {"name": "Desbloquear PDF", "route": "/convert/pdf-unlock", "accept": ".pdf", "aliases": "remover senha pdf destravar pdf unlock pdf"},
        {"name": "Extrair imagens do PDF", "route": "/convert/pdf-extract-images", "accept": ".pdf", "aliases": "extrair fotos imagens de pdf exportar imagens"},
        {"name": "Editar PDF", "route": "/convert/pdf-edit", "accept": ".pdf"},
        {"name": "CSV -> XLSX", "route": "/convert/csv-to-xlsx", "accept": ".csv"},
        {"name": "DOC -> DOCX", "route": "/convert/doc-to-docx", "accept": ".doc"},
        {"name": "DOC -> PDF", "route": "/convert/doc-to-pdf", "accept": ".doc"},
        {"name": "DOCX -> PDF", "route": "/convert/docx-to-pdf", "accept": ".docx"},
        {"name": "DOCX -> TXT", "route": "/convert/docx-to-txt", "accept": ".docx"},
        {"name": "DOCX -> XLSX", "route": "/convert/docx-to-xlsx", "accept": ".docx"},
        {"name": "Arquivos -> ZIP", "route": "/convert/files-to-zip", "accept": ".pdf,.doc,.docx,.odt,.ppt,.pptx,.odp,.xls,.xlsx,.ods,.txt,.csv,.json,.md,.html,.jpg,.jpeg,.png,.webp,.heic,.svg,.mp3,.wav,.mp4,.mov,.mkv,.avi,.webm,.zip", "multiple": True, "description": "Compacte documentos, imagens, audio e video em um arquivo ZIP.", "icon": "archive", "aliases": "zip compactar arquivos comprimir pasta arquivo pacote download"},
        {"name": "HTML -> DOCX", "route": "/convert/html-to-docx", "accept": ".html,.htm"},
        {"name": "HTML -> PDF", "route": "/convert/html-to-pdf", "accept": ".html,.htm"},
        {"name": "JPG -> PDF", "route": "/convert/jpg-to-pdf", "accept": ".jpg,.jpeg"},
        {"name": "JSON -> CSV", "route": "/convert/json-to-csv", "accept": ".json"},
        {"name": "JSON -> XLSX", "route": "/convert/json-to-xlsx", "accept": ".json"},
        {"name": "MD -> DOCX", "route": "/convert/md-to-docx", "accept": ".md"},
        {"name": "MD -> PDF", "route": "/convert/md-to-pdf", "accept": ".md"},
        {"name": "ODP -> PDF", "route": "/convert/odp-to-pdf", "accept": ".odp"},
        {"name": "ODP -> PPTX", "route": "/convert/odp-to-pptx", "accept": ".odp"},
        {"name": "ODS -> PDF", "route": "/convert/ods-to-pdf", "accept": ".ods"},
        {"name": "ODS -> XLSX", "route": "/convert/ods-to-xlsx", "accept": ".ods"},
        {"name": "ODT -> DOCX", "route": "/convert/odt-to-docx", "accept": ".odt"},
        {"name": "ODT -> PDF", "route": "/convert/odt-to-pdf", "accept": ".odt"},
        {"name": "PDF -> CSV", "route": "/convert/pdf-to-csv", "accept": ".pdf"},
        {"name": "PDF -> DOCX", "route": "/convert/pdf-to-docx", "accept": ".pdf"},
        {"name": "PDF -> HTML", "route": "/convert/pdf-to-html", "accept": ".pdf"},
        {"name": "PDF -> JPG", "route": "/convert/pdf-to-jpg", "accept": ".pdf"},
        {"name": "PDF -> PNG", "route": "/convert/pdf-to-png", "accept": ".pdf"},
        {"name": "PDF -> PPTX", "route": "/convert/pdf-to-pptx", "accept": ".pdf", "aliases": "pdf para powerpoint pdf para slides pdf para apresentacao"},
        {"name": "PDF -> TXT", "route": "/convert/pdf-to-txt", "accept": ".pdf"},
        {"name": "PDF -> XLSX", "route": "/convert/pdf-to-xlsx", "accept": ".pdf"},
        {"name": "PPT -> PDF", "route": "/convert/ppt-to-pdf", "accept": ".ppt"},
        {"name": "PPT -> PPTX", "route": "/convert/ppt-to-pptx", "accept": ".ppt"},
        {"name": "PPTX -> PDF", "route": "/convert/pptx-to-pdf", "accept": ".pptx"},
        {"name": "TXT -> DOCX", "route": "/convert/txt-to-docx", "accept": ".txt"},
        {"name": "TXT -> PDF", "route": "/convert/txt-to-pdf", "accept": ".txt"},
        {"name": "XLS -> PDF", "route": "/convert/xls-to-pdf", "accept": ".xls"},
        {"name": "XLS -> XLSX", "route": "/convert/xls-to-xlsx", "accept": ".xls"},
        {"name": "XLSX -> CSV", "route": "/convert/xlsx-to-csv", "accept": ".xlsx"},
        {"name": "XLSX -> DOCX", "route": "/convert/xlsx-to-docx", "accept": ".xlsx"},
        {"name": "XLSX -> JSON", "route": "/convert/xlsx-to-json", "accept": ".xlsx"},
        {"name": "XLSX -> PDF", "route": "/convert/xlsx-to-pdf", "accept": ".xlsx"},
    ],
    "Imagens": [
        {"name": "HEIC -> JPG", "route": "/convert/heic-to-jpg", "accept": ".heic"},
        {"name": "HEIC -> PNG", "route": "/convert/heic-to-png", "accept": ".heic"},
        {"name": "Imagens -> PDF", "route": "/convert/images-to-pdf", "accept": ".jpg,.jpeg,.png,.webp,.heic", "multiple": True, "description": "Transforme uma ou varias imagens em um unico PDF.", "icon": "file-image", "aliases": "imagem para pdf imagens para pdf foto para pdf jpg png webp heic scanner"},
        {"name": "JPG -> PNG", "route": "/convert/jpg-to-png", "accept": ".jpg,.jpeg"},
        {"name": "JPG -> SVG", "route": "/convert/jpg-to-svg", "accept": ".jpg,.jpeg"},
        {"name": "JPG -> WEBP", "route": "/convert/jpg-to-webp", "accept": ".jpg,.jpeg"},
        {"name": "PNG -> JPG", "route": "/convert/png-to-jpg", "accept": ".png"},
        {"name": "PNG -> SVG", "route": "/convert/png-to-svg", "accept": ".png"},
        {"name": "PNG -> WEBP", "route": "/convert/png-to-webp", "accept": ".png"},
        {"name": "SVG -> JPG", "route": "/convert/svg-to-jpg", "accept": ".svg"},
        {"name": "SVG -> PNG", "route": "/convert/svg-to-png", "accept": ".svg"},
        {"name": "WEBP -> JPG", "route": "/convert/webp-to-jpg", "accept": ".webp"},
        {"name": "WEBP -> PNG", "route": "/convert/webp-to-png", "accept": ".webp"},
    ],
    "Videos": [
        {"name": "Baixar video do YouTube", "route": "/tools/youtube-download", "page_route": "/tools/youtube-download", "accept": "URL do YouTube", "description": "Cole o link do YouTube e baixe em MP4.", "badge": "Novo", "icon": "video", "aliases": "youtube baixar video download mp4 link url"},
        {"name": "AVI -> MP4", "route": "/convert/avi-to-mp4", "accept": ".avi"},
        {"name": "MKV -> MP4", "route": "/convert/mkv-to-mp4", "accept": ".mkv"},
        {"name": "MOV -> MP4", "route": "/convert/mov-to-mp4", "accept": ".mov"},
        {"name": "MP4 -> GIF", "route": "/convert/mp4-to-gif", "accept": ".mp4"},
        {"name": "MP4 -> MKV", "route": "/convert/mp4-to-mkv", "accept": ".mp4"},
        {"name": "MP4 -> MOV", "route": "/convert/mp4-to-mov", "accept": ".mp4"},
        {"name": "MP4 -> MP3", "route": "/convert/mp4-to-mp3", "accept": ".mp4"},
        {"name": "MP4 -> WAV", "route": "/convert/mp4-to-wav", "accept": ".mp4"},
        {"name": "MP4 -> WEBM", "route": "/convert/mp4-to-webm", "accept": ".mp4"},
        {"name": "WEBM -> MP4", "route": "/convert/webm-to-mp4", "accept": ".webm"},
    ],
}


def get_pdf_tool_count():
    return sum(
        1
        for tool in TOOLS["Documentos"]
        if "pdf" in tool["route"] or "PDF" in tool["name"] or ".pdf" in tool.get("accept", "")
    )


def build_tool_counts():
    categories = {category: len(tools) for category, tools in TOOLS.items()}
    total = sum(categories.values())
    visible_in_mega_menu = {
        "pdf": 5,
        "Imagens": 5,
        "Videos": 4,
        "Audios": 4,
    }
    mega_totals = {
        "pdf": get_pdf_tool_count(),
        "Imagens": categories["Imagens"],
        "Videos": categories["Videos"],
        "Audios": categories["Audios"],
    }

    return {
        "total": total,
        "categories": categories,
        "mega_totals": mega_totals,
        "mega_remaining": {
            name: max(count - visible_in_mega_menu.get(name, 0), 0)
            for name, count in mega_totals.items()
        },
    }
