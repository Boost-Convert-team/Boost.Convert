from datetime import timedelta
from models import utc_now
from Blueprints.services.privacy.file_retention import (
    cleanup_expired_ai_transcripts,
    cleanup_expired_conversion_files,
    get_cleanup_interval_minutes,
)

LAST_CLEANUP_AT = None

def run_conversion_file_cleanup(app):
    global LAST_CLEANUP_AT
    now = utc_now()
    interval_minutes = get_cleanup_interval_minutes(app)

    if LAST_CLEANUP_AT is not None and now < LAST_CLEANUP_AT + timedelta(minutes=interval_minutes): return
    LAST_CLEANUP_AT = now
    
    try:
        cleanup_expired_conversion_files(app)
        cleanup_expired_ai_transcripts(app)
    except Exception:
        app.logger.error("Erro ao limpar arquivos temporarios de conversao", exc_info=False)
