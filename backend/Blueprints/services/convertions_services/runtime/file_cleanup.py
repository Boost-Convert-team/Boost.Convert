from datetime import timedelta

from models import utc_now
from Blueprints.services.privacy.file_retention import (
    cleanup_expired_conversion_files,
    get_cleanup_interval_minutes,
)

_last_cleanup_at = None

def run_conversion_file_cleanup(app):
    global _last_cleanup_at

    now = utc_now()
    interval_minutes = get_cleanup_interval_minutes(app)

    next_cleanup_at = (
        _last_cleanup_at + timedelta(minutes=interval_minutes)
        if _last_cleanup_at is not None
        else None
    )
    if next_cleanup_at is not None and now < next_cleanup_at:
        return

    _last_cleanup_at = now

    try:
        cleanup_expired_conversion_files(app)
    except Exception:
        app.logger.error("Erro ao limpar arquivos temporarios de conversao", exc_info=False)
