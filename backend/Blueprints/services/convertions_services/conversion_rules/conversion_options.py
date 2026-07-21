Option = dict[str, object]


def choice(value: str, label: str) -> dict[str, str]:
    return {"value": value, "label": label}


def select_option(
    name: str,
    label: str,
    default: str,
    choices: list[dict[str, str]],
) -> Option:
    return {
        "name": name,
        "label": label,
        "type": "select",
        "default": default,
        "choices": choices,
    }


AUDIO_BITRATE_OPTION = select_option(
    "audio_bitrate",
    "Qualidade do MP3",
    "320k",
    [
        choice("128k", "128 kbps"),
        choice("192k", "192 kbps"),
        choice("256k", "256 kbps"),
        choice("320k", "320 kbps"),
    ],
)
AUDIO_SAMPLE_RATE_OPTION = select_option(
    "sample_rate",
    "Taxa de amostragem",
    "original",
    [
        choice("original", "Original"),
        choice("44100", "44.1 kHz"),
        choice("48000", "48 kHz"),
    ],
)
IMAGE_QUALITY_OPTION = select_option(
    "image_quality",
    "Qualidade do JPEG",
    "95",
    [
        choice("70", "Menor arquivo"),
        choice("85", "Equilibrada"),
        choice("95", "Alta qualidade"),
    ],
)
GIF_FPS_OPTION = select_option(
    "gif_fps",
    "Frames por segundo",
    "10",
    [
        choice("original", "Original"),
        choice("10", "10 fps"),
        choice("15", "15 fps"),
        choice("24", "24 fps"),
    ],
)
GIF_WIDTH_OPTION = select_option(
    "gif_width",
    "Largura do GIF",
    "480",
    [
        choice("original", "Original"),
        choice("480", "480 px"),
        choice("720", "720 px"),
        choice("1080", "1080 px"),
    ],
)
GIF_DURATION_OPTION = select_option(
    "gif_duration",
    "Duracao do GIF",
    "10",
    [
        choice("5", "5 segundos"),
        choice("10", "10 segundos"),
        choice("15", "15 segundos"),
        choice("original", "Original"),
    ],
)
VIDEO_QUALITY_OPTION = select_option(
    "video_quality",
    "Qualidade do video",
    "high",
    [
        choice("smaller", "Menor arquivo"),
        choice("balanced", "Equilibrada"),
        choice("high", "Alta qualidade"),
    ],
)
WEBM_QUALITY_OPTION = select_option(
    "video_quality",
    "Qualidade do video",
    "balanced",
    [
        choice("smaller", "Menor arquivo"),
        choice("balanced", "Equilibrada"),
        choice("high", "Alta qualidade"),
    ],
)
PDF_COMPRESSION_OPTION = select_option(
    "compression_level",
    "Nivel de compressao",
    "balanced",
    [
        choice("light", "Leve"),
        choice("balanced", "Equilibrada"),
        choice("strong", "Forte"),
    ],
)
PDF_ROTATION_OPTION = select_option(
    "rotation_angle",
    "Rotacao",
    "90",
    [
        choice("90", "90 graus"),
        choice("180", "180 graus"),
        choice("270", "270 graus"),
    ],
)

PDF_PAGE_RANGES_OPTION: Option = {
    "name": "page_ranges",
    "label": "Paginas ou intervalos",
    "type": "text",
    "default": "",
    "placeholder": "Ex: 1-3,5,8-10. Vazio separa todas as paginas.",
}
PDF_PASSWORD_OPTION: Option = {
    "name": "pdf_password",
    "label": "Senha do PDF",
    "type": "text",
    "default": "",
    "placeholder": "Senha",
}
PDF_EDIT_TEXT_OPTION: Option = {
    "name": "edit_text",
    "label": "Texto para adicionar",
    "type": "text",
    "default": "",
    "placeholder": "Texto que sera inserido no PDF",
}
PDF_EDIT_PAGE_OPTION: Option = {
    "name": "edit_page",
    "label": "Pagina",
    "type": "number",
    "default": "1",
    "min": "1",
    "step": "1",
}
PDF_EDIT_X_OPTION: Option = {
    "name": "x_position",
    "label": "Posicao X",
    "type": "number",
    "default": "72",
    "min": "0",
    "step": "1",
}
PDF_EDIT_Y_OPTION: Option = {
    "name": "y_position",
    "label": "Posicao Y",
    "type": "number",
    "default": "72",
    "min": "0",
    "step": "1",
}
PDF_EDIT_FONT_SIZE_OPTION: Option = {
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
VIDEO_ROUTES = {
    "/convert/avi-to-mp4",
    "/convert/mkv-to-mp4",
    "/convert/mov-to-mp4",
    "/convert/mp4-to-mkv",
    "/convert/mp4-to-mov",
    "/convert/mp4-to-webm",
    "/convert/webm-to-mp4",
}

CONVERSION_OPTIONS_BY_ROUTE = {
    **{route: (AUDIO_BITRATE_OPTION,) for route in MP3_ROUTES},
    **{route: (AUDIO_SAMPLE_RATE_OPTION,) for route in WAV_ROUTES},
    **{route: (IMAGE_QUALITY_OPTION,) for route in JPG_ROUTES},
    **{route: (VIDEO_QUALITY_OPTION,) for route in VIDEO_ROUTES},
    "/convert/pdf-split": (PDF_PAGE_RANGES_OPTION,),
    "/convert/pdf-compress": (PDF_COMPRESSION_OPTION,),
    "/convert/pdf-rotate": (PDF_ROTATION_OPTION, PDF_PAGE_RANGES_OPTION),
    "/convert/pdf-protect": (PDF_PASSWORD_OPTION,),
    "/convert/pdf-unlock": (PDF_PASSWORD_OPTION,),
    "/convert/pdf-edit": (
        PDF_EDIT_TEXT_OPTION,
        PDF_EDIT_PAGE_OPTION,
        PDF_EDIT_X_OPTION,
        PDF_EDIT_Y_OPTION,
        PDF_EDIT_FONT_SIZE_OPTION,
    ),
    "/convert/mp4-to-gif": (
        GIF_FPS_OPTION,
        GIF_WIDTH_OPTION,
        GIF_DURATION_OPTION,
    ),
    "/convert/mp4-to-webm": (WEBM_QUALITY_OPTION,),
}


def get_conversion_options(route: str) -> list[Option]:
    return list(CONVERSION_OPTIONS_BY_ROUTE.get(route, ()))


def sanitize_conversion_options(route: str, form) -> dict[str, object]:
    sanitized = {}
    for option in get_conversion_options(route):
        name = str(option["name"])
        value = form.get(name, option["default"])

        if option["type"] == "select":
            choices = option["choices"]
            allowed_values = {choice["value"] for choice in choices}
            if value not in allowed_values:
                value = option["default"]
        elif option["type"] == "number":
            value = sanitize_number_option(value, option)
        elif option["type"] == "text":
            value = str(value).strip()[:500]

        sanitized[name] = value
    return sanitized


def sanitize_number_option(value, option: Option) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = int(option["default"])

    if option.get("min") is not None:
        number = max(number, int(option["min"]))
    if option.get("max") is not None:
        number = min(number, int(option["max"]))
    return str(number)
