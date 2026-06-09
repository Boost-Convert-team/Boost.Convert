SENSITIVE_OPTION_NAMES = {"pdf_password", "edit_text"}
REDACTED_OPTION_VALUE = "removido_por_privacidade"


def get_persistable_conversion_options(options):
    persistable = {}

    for name, value in (options or {}).items():
        if name in SENSITIVE_OPTION_NAMES:
            persistable[name] = REDACTED_OPTION_VALUE if value else ""
            continue
        persistable[name] = value

    return persistable


def get_runtime_conversion_options(options):
    return dict(options or {})
