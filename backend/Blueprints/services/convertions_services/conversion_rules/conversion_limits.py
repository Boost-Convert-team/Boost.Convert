import os

from Blueprints.services.access.access_service import (
    FREE_DAILY_LIMIT,
    FREE_PLAN,
    PLANS,
    PRO_PLAN,
    is_pro_user,
)


BYTES_PER_MB = 1024 * 1024

CONVERSION_CATEGORIES = {
    "audios": {"aac", "flac", "mp3", "ogg", "wav", "wma"},
    "documents": {
        "csv",
        "doc",
        "docx",
        "html",
        "htm",
        "json",
        "md",
        "odp",
        "ods",
        "odt",
        "pdf",
        "ppt",
        "pptx",
        "txt",
        "xls",
        "xlsx",
        "zip",
    },
    "images": {"heic", "jpg", "jpeg", "png", "svg", "webp"},
    "videos": {"avi", "mkv", "mov", "mp4", "webm"},
}

UPLOAD_LIMITS_MB = {
    FREE_PLAN: {"documents": 50, "images": 25, "audios": 100, "videos": 250},
    PRO_PLAN: {"documents": 300, "images": 150, "audios": 500, "videos": 2048},
}

# Files per upload for tools that convert each file separately.
MULTI_FILE_LIMITS = {FREE_PLAN: 2, PRO_PLAN: 15}

# Tools that combine many files into one result get their own, larger limits.
# They stay 20-30% above iLovePDF (Merge PDF: 25 Free / 500 Premium,
# Image to PDF: 20 Free / 80 Premium on ilovepdf.com/pricing, October 2026).
TOOL_FILE_COUNT_LIMITS = {
    "pdf_merge": {FREE_PLAN: 32, PRO_PLAN: 650},
    "images_to_pdf": {FREE_PLAN: 25, PRO_PLAN: 100},
}

SPECIAL_ROUTE_EXTENSIONS = {
    "/convert/pdf-merge": ("pdf", "pdf"),
    "/convert/pdf-split": ("pdf", "zip"),
    "/convert/pdf-compress": ("pdf", "pdf"),
    "/convert/pdf-edit": ("pdf", "pdf"),
    "/convert/pdf-rotate": ("pdf", "pdf"),
    "/convert/pdf-protect": ("pdf", "pdf"),
    "/convert/pdf-unlock": ("pdf", "pdf"),
    "/convert/pdf-extract-images": ("pdf", "zip"),
    "/convert/files-to-zip": ("zip", "zip"),
    "/convert/images-to-pdf": ("jpg", "pdf"),
}

CATEGORY_LABELS = {
    "audios": "audios",
    "documents": "documentos",
    "images": "imagens",
    "videos": "videos",
}


def get_plan_name(usuario) -> str:
    return PRO_PLAN if is_pro_user(usuario) else FREE_PLAN


def get_conversion_category(input_extension: str, output_extension: str) -> str:
    input_extension = input_extension.lower()
    output_extension = output_extension.lower()

    if input_extension in CONVERSION_CATEGORIES["videos"]:
        return "videos"
    if input_extension in CONVERSION_CATEGORIES["audios"]:
        return "audios"
    if input_extension in CONVERSION_CATEGORIES["documents"]:
        return "documents"
    if input_extension in CONVERSION_CATEGORIES["images"]:
        if output_extension in CONVERSION_CATEGORIES["documents"]:
            return "documents"
        return "images"
    return "documents"


def get_upload_limit_mb(usuario, input_extension: str, output_extension: str):
    plan_name = get_plan_name(usuario)
    category = get_conversion_category(input_extension, output_extension)
    return UPLOAD_LIMITS_MB[plan_name][category], category, plan_name


def get_file_size(file) -> int:
    current_position = file.stream.tell()
    try:
        file.stream.seek(0, os.SEEK_END)
        return file.stream.tell()
    finally:
        file.stream.seek(current_position)


def validate_upload_size(file, usuario, input_extension: str, output_extension: str):
    limit_mb, category, plan_name = get_upload_limit_mb(
        usuario,
        input_extension,
        output_extension,
    )
    if get_file_size(file) <= limit_mb * BYTES_PER_MB:
        return True, None

    return (
        False,
        f"Arquivo muito grande para o plano {plan_name}. "
        f"Limite para {category}: {limit_mb} MB.",
    )


def get_file_count_limits(tool_name: str | None) -> dict[str, int]:
    return TOOL_FILE_COUNT_LIMITS.get(tool_name, MULTI_FILE_LIMITS)


def validate_multi_file_count(files, usuario, tool_name: str | None = None):
    plan_name = get_plan_name(usuario)
    limit = get_file_count_limits(tool_name)[plan_name]
    if len(files) <= limit:
        return True, None

    return (
        False,
        f"Voce enviou {len(files)} arquivos. "
        f"Limite do plano {plan_name}: {limit} arquivos.",
    )


def get_tool_extensions(route: str) -> tuple[str, str]:
    if route in SPECIAL_ROUTE_EXTENSIONS:
        return SPECIAL_ROUTE_EXTENSIONS[route]

    slug = route.replace("/convert/", "", 1)
    if "-to-" not in slug:
        return "pdf", "pdf"
    return tuple(slug.split("-to-", 1))


def format_limit_mb(limit_mb: int) -> str:
    if limit_mb >= 1024 and limit_mb % 1024 == 0:
        return f"{limit_mb // 1024} GB"
    return f"{limit_mb} MB"


def get_tool_name(route: str) -> str:
    """`/convert/pdf-merge` is handled by the tool named `pdf_merge`."""
    return route.replace("/convert/", "", 1).replace("-", "_")


def get_tool_limit_info(tool: dict[str, object]) -> dict[str, object]:
    route = str(tool["route"])
    input_extension, output_extension = get_tool_extensions(route)
    category = get_conversion_category(input_extension, output_extension)
    free_limit = UPLOAD_LIMITS_MB[FREE_PLAN][category]
    pro_limit = UPLOAD_LIMITS_MB[PRO_PLAN][category]
    file_count_limits = get_file_count_limits(get_tool_name(route))
    return {
        "category": category,
        "category_label": CATEGORY_LABELS.get(category, category),
        "free_daily_limit": FREE_DAILY_LIMIT,
        "free_upload_limit_mb": free_limit,
        "free_upload_limit_label": format_limit_mb(free_limit),
        "pro_upload_limit_mb": pro_limit,
        "pro_upload_limit_label": format_limit_mb(pro_limit),
        "free_file_count_limit": file_count_limits[FREE_PLAN],
        "pro_file_count_limit": file_count_limits[PRO_PLAN],
    }


def get_plan_limits() -> dict[str, dict[str, object]]:
    """Limits shown on the pricing and account pages, from the same constants the uploads enforce."""
    return {
        plan: {
            "daily_conversions": FREE_DAILY_LIMIT if plan == FREE_PLAN else None,
            "files_per_upload": MULTI_FILE_LIMITS[plan],
            "merge_pdf_files": TOOL_FILE_COUNT_LIMITS["pdf_merge"][plan],
            "images_to_pdf_files": TOOL_FILE_COUNT_LIMITS["images_to_pdf"][plan],
            "upload_labels": {
                category: format_limit_mb(limit_mb)
                for category, limit_mb in UPLOAD_LIMITS_MB[plan].items()
            },
        }
        for plan in PLANS
    }
