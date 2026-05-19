AUDIO_BITRATE_OPTION = {
    "name": "audio_bitrate",
    "label": "Qualidade do MP3",
    "type": "select",
    "default": "192k",
    "choices": [
        {"value": "128k", "label": "128 kbps"},
        {"value": "192k", "label": "192 kbps"},
        {"value": "256k", "label": "256 kbps"},
        {"value": "320k", "label": "320 kbps"},
    ],
}

AUDIO_SAMPLE_RATE_OPTION = {
    "name": "sample_rate",
    "label": "Taxa de amostragem",
    "type": "select",
    "default": "original",
    "choices": [
        {"value": "original", "label": "Original"},
        {"value": "44100", "label": "44.1 kHz"},
        {"value": "48000", "label": "48 kHz"},
    ],
}

IMAGE_QUALITY_OPTION = {
    "name": "image_quality",
    "label": "Qualidade da imagem",
    "type": "select",
    "default": "85",
    "choices": [
        {"value": "70", "label": "Menor arquivo"},
        {"value": "85", "label": "Equilibrada"},
        {"value": "95", "label": "Alta qualidade"},
    ],
}

GIF_FPS_OPTION = {
    "name": "gif_fps",
    "label": "Frames por segundo",
    "type": "select",
    "default": "10",
    "choices": [
        {"value": "10", "label": "10 fps"},
        {"value": "15", "label": "15 fps"},
        {"value": "24", "label": "24 fps"},
    ],
}

GIF_WIDTH_OPTION = {
    "name": "gif_width",
    "label": "Largura do GIF",
    "type": "select",
    "default": "480",
    "choices": [
        {"value": "480", "label": "480 px"},
        {"value": "720", "label": "720 px"},
        {"value": "1080", "label": "1080 px"},
    ],
}

VIDEO_QUALITY_OPTION = {
    "name": "video_quality",
    "label": "Qualidade do video",
    "type": "select",
    "default": "balanced",
    "choices": [
        {"value": "smaller", "label": "Menor arquivo"},
        {"value": "balanced", "label": "Equilibrada"},
        {"value": "high", "label": "Alta qualidade"},
    ],
}

PDF_COMPRESSION_OPTION = {
    "name": "compression_level",
    "label": "Nivel de compressao",
    "type": "select",
    "default": "balanced",
    "choices": [
        {"value": "light", "label": "Leve"},
        {"value": "balanced", "label": "Equilibrada"},
        {"value": "strong", "label": "Forte"},
    ],
}

PDF_PAGE_RANGES_OPTION = {
    "name": "page_ranges",
    "label": "Paginas ou intervalos",
    "type": "text",
    "default": "",
    "placeholder": "Ex: 1-3,5,8-10. Vazio separa todas as paginas.",
}

PDF_EDIT_TEXT_OPTION = {
    "name": "edit_text",
    "label": "Texto para adicionar",
    "type": "text",
    "default": "",
    "placeholder": "Texto que sera inserido no PDF",
}

PDF_EDIT_PAGE_OPTION = {
    "name": "edit_page",
    "label": "Pagina",
    "type": "number",
    "default": "1",
    "min": "1",
    "step": "1",
}

PDF_EDIT_X_OPTION = {
    "name": "x_position",
    "label": "Posicao X",
    "type": "number",
    "default": "72",
    "min": "0",
    "step": "1",
}

PDF_EDIT_Y_OPTION = {
    "name": "y_position",
    "label": "Posicao Y",
    "type": "number",
    "default": "72",
    "min": "0",
    "step": "1",
}

PDF_EDIT_FONT_SIZE_OPTION = {
    "name": "font_size",
    "label": "Tamanho da fonte",
    "type": "number",
    "default": "14",
    "min": "6",
    "max": "72",
    "step": "1",
}

MP3_ROUTES = {
    "/convert/aac-to-mp3",
    "/convert/flac-to-mp3",
    "/convert/ogg-to-mp3",
    "/convert/wav-to-mp3",
    "/convert/wma-to-mp3",
    "/convert/mp4-to-mp3",
}

WAV_ROUTES = {
    "/convert/flac-to-wav",
    "/convert/mp3-to-wav",
    "/convert/ogg-to-wav",
    "/convert/mp4-to-wav",
}

JPG_ROUTES = {
    "/convert/heic-to-jpg",
    "/convert/png-to-jpg",
    "/convert/svg-to-jpg",
    "/convert/webp-to-jpg",
}

WEBP_ROUTES = {
    "/convert/jpg-to-webp",
    "/convert/png-to-webp",
}

VIDEO_ROUTES = {
    "/convert/avi-to-mp4",
    "/convert/mkv-to-mp4",
    "/convert/mov-to-mp4",
    "/convert/mp4-to-mkv",
    "/convert/mp4-to-mov",
    "/convert/mp4-to-webm",
    "/convert/webm-to-mp4",
}

def get_conversion_options(route):
    if route == "/convert/pdf-split":
        return [PDF_PAGE_RANGES_OPTION]

    if route == "/convert/pdf-compress":
        return [PDF_COMPRESSION_OPTION]

    if route == "/convert/pdf-edit":
        return [
            PDF_EDIT_TEXT_OPTION,
            PDF_EDIT_PAGE_OPTION,
            PDF_EDIT_X_OPTION,
            PDF_EDIT_Y_OPTION,
            PDF_EDIT_FONT_SIZE_OPTION,
        ]

    if route in MP3_ROUTES:
        return [AUDIO_BITRATE_OPTION]

    if route in WAV_ROUTES:
        return [AUDIO_SAMPLE_RATE_OPTION]

    if route in JPG_ROUTES or route in WEBP_ROUTES:
        return [IMAGE_QUALITY_OPTION]

    if route == "/convert/mp4-to-gif":
        return [GIF_FPS_OPTION, GIF_WIDTH_OPTION]

    if route in VIDEO_ROUTES:
        return [VIDEO_QUALITY_OPTION]

    return []

def sanitize_conversion_options(route, form):
    sanitized = {}

    for option in get_conversion_options(route):
        name = option["name"]
        value = form.get(name, option["default"])

        if option["type"] == "select":
            allowed_values = {choice["value"] for choice in option["choices"]}
            if value not in allowed_values:
                value = option["default"]

        elif option["type"] == "number":
            value = sanitize_number_option(value, option)

        elif option["type"] == "text":
            value = str(value).strip()[:500]

        sanitized[name] = value

    return sanitized

def sanitize_number_option(value, option):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = int(option["default"])

    if option.get("min") is not None:
        number = max(number, int(option["min"]))

    if option.get("max") is not None:
        number = min(number, int(option["max"]))

    return str(number)
