import os

from Blueprints.services.subscription.subscription_service import has_active_pro_subscription

CONVERSION_CATEGORIES = {
    "audios": {"aac", "flac", "mp3", "ogg", "wav", "wma"},
    "documents": {"csv", "docx", "html", "htm", "json", "md", "pdf", "pptx", "txt", "xlsx"},
    "images": {"heic", "jpg", "jpeg", "png", "svg", "webp"},
    "videos": {"avi", "mkv", "mov", "mp4", "webm"},
}

UPLOAD_LIMITS_MB = {
    "free": {
        "documents": 50,
        "images": 25,
        "audios": 100,
        "videos": 250,
    },
    "pro": {
        "documents": 300,
        "images": 150,
        "audios": 500,
        "videos": 2048,
    },
}

MULTI_FILE_LIMITS = {
    "free": 2,
    "pro": 15,
}

SPECIAL_ROUTE_EXTENSIONS = {
    "/convert/pdf-merge": ("pdf", "pdf"),
    "/convert/pdf-split": ("pdf", "zip"),
    "/convert/pdf-compress": ("pdf", "pdf"),
    "/convert/pdf-edit": ("pdf", "pdf"),
}

CATEGORY_LABELS = {
    "audios": "audios",
    "documents": "documentos",
    "images": "imagens",
    "videos": "videos",
}

def get_plan_name(usuario):
    if has_active_pro_subscription(usuario): return "pro"

    return "free"

def get_conversion_category(input_extension, output_extension):
    input_extension = input_extension.lower()
    output_extension = output_extension.lower()

    if input_extension in CONVERSION_CATEGORIES["videos"]: return "videos"
    if input_extension in CONVERSION_CATEGORIES["audios"]: return "audios"
    if input_extension in CONVERSION_CATEGORIES["documents"]: return "documents"
    if input_extension in CONVERSION_CATEGORIES["images"]:
        if output_extension in CONVERSION_CATEGORIES["documents"]: return "documents"
        return "images"

    return "documents"

def get_upload_limit_mb(usuario, input_extension, output_extension):
    plan_name = get_plan_name(usuario)
    category = get_conversion_category(input_extension, output_extension)

    return UPLOAD_LIMITS_MB[plan_name][category], category, plan_name

def get_file_size(file):
    current_position = file.stream.tell()

    try:
        file.stream.seek(0, os.SEEK_END)
        size = file.stream.tell()
    finally:
        file.stream.seek(current_position)

    return size

def validate_upload_size(file, usuario, input_extension, output_extension):
    limit_mb, category, plan_name = get_upload_limit_mb(usuario, input_extension, output_extension)
    limit_bytes = limit_mb * 1024 * 1024
    file_size = get_file_size(file)

    if file_size > limit_bytes:
        return (
            False,
            f"Arquivo muito grande para o plano {plan_name}. "
            f"Limite para {category}: {limit_mb} MB.",
        )

    return True, None

def validate_multi_file_count(files, usuario):
    plan_name = get_plan_name(usuario)
    limit = MULTI_FILE_LIMITS[plan_name]
    file_count = len(files)

    if file_count > limit:
        return (
            False,
            f"Voce enviou {file_count} arquivos. "
            f"Limite do plano {plan_name}: {limit} arquivos.",
        )

    return True, None

def get_tool_limit_info(tool):
    input_extension, output_extension = get_tool_extensions(tool["route"])
    category = get_conversion_category(input_extension, output_extension)

    info = {
        "category": category,
        "category_label": CATEGORY_LABELS.get(category, category),
        "free_daily_limit": get_free_daily_limit(),
        "free_upload_limit_mb": UPLOAD_LIMITS_MB["free"][category],
        "free_upload_limit_label": format_limit_mb(UPLOAD_LIMITS_MB["free"][category]),
        "pro_upload_limit_mb": UPLOAD_LIMITS_MB["pro"][category],
        "pro_upload_limit_label": format_limit_mb(UPLOAD_LIMITS_MB["pro"][category]),
        "is_multiple": True,
        "free_file_count_limit": MULTI_FILE_LIMITS["free"],
        "pro_file_count_limit": MULTI_FILE_LIMITS["pro"],
    }

    return info

def get_tools_with_limit_info(tools):
    tools_with_limits = {}

    for category, category_tools in tools.items():
        tools_with_limits[category] = []

        for tool in category_tools:
            tool_with_limits = dict(tool)
            tool_with_limits["limits"] = get_tool_limit_info(tool)
            tools_with_limits[category].append(tool_with_limits)

    return tools_with_limits

def get_tool_extensions(route):
    if route in SPECIAL_ROUTE_EXTENSIONS:
        return SPECIAL_ROUTE_EXTENSIONS[route]

    slug = route.replace("/convert/", "", 1)

    if "-to-" not in slug:
        return "pdf", "pdf"

    input_extension, output_extension = slug.split("-to-", 1)
    return input_extension, output_extension

def format_limit_mb(limit_mb):
    if limit_mb >= 1024 and limit_mb % 1024 == 0:
        return f"{limit_mb // 1024} GB"

    return f"{limit_mb} MB"

def get_free_daily_limit():
    from Blueprints.services.subscription.access_service import FREE_DAILY_LIMIT

    return FREE_DAILY_LIMIT
