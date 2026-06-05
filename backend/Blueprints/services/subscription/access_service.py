from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from extensions import db
from models import DailyUsage
from Blueprints.services.subscription.subscription_service import has_active_pro_subscription

FREE_DAILY_LIMIT = 10
FREE_USAGE_WINDOW = timedelta(hours=24)

@dataclass(frozen=True)
class UsageStatus:
    used: int
    limit: int | None
    remaining: int | str
    percent: int
    reset_at: datetime | None
    reset_in: str | None
    is_limited: bool

def utc_now(): return datetime.now(timezone.utc)
def as_utc(value):
    if value is None: return None
    if value.tzinfo is None: return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
def is_pro_user(usuario): return has_active_pro_subscription(usuario)
def get_usage_identity(usuario=None, session_id=None):
    if usuario is not None: return "user", usuario.id
    if session_id is None: raise ValueError("session_id is required for anonymous users")
    return "session", session_id
def lock_usage_identity(usuario=None, session_id=None):
    identity_type, identity_value = get_usage_identity(usuario=usuario, session_id=session_id)
    bind = db.session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        db.session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:usage_key))"), {"usage_key": f"usage:{identity_type}:{identity_value}"})
def get_usage_record(usuario=None, session_id=None, for_update=False):
    query = DailyUsage.query
    if usuario is not None:
        query = query.filter(DailyUsage.user_id == usuario.id)
    else:
        if session_id is None: raise ValueError("session_id is required for anonymous users")
        query = query.filter(DailyUsage.session_id == session_id)
    if for_update: query = query.with_for_update()
    return query.order_by(DailyUsage.id.desc()).first()
def create_usage_record(usuario=None, session_id=None, now=None):
    now = now or utc_now()
    usage = DailyUsage()
    usage.user_id = usuario.id if usuario is not None else None
    usage.session_id = session_id if usuario is None else None
    usage.usage_date = now.date()
    usage.window_started_at = now
    usage.usage_count = 0
    db.session.add(usage)
    db.session.flush()
    return usage
def get_or_create_usage_record(usuario=None, session_id=None, now=None, for_update=False):
    usage = get_usage_record(usuario=usuario, session_id=session_id, for_update=for_update)
    if usage is not None: return usage
    return create_usage_record(usuario=usuario, session_id=session_id, now=now)
def reset_usage_window(usage, now):
    usage.window_started_at = now
    usage.usage_date = now.date()
    usage.usage_count = 0
def ensure_active_window(usage, now):
    window_started_at = as_utc(usage.window_started_at)
    if window_started_at is None or now >= window_started_at + FREE_USAGE_WINDOW:
        reset_usage_window(usage, now)
        return
    usage.window_started_at = window_started_at
def get_reset_at(usage):
    window_started_at = as_utc(usage.window_started_at)
    if window_started_at is None: return None
    return window_started_at + FREE_USAGE_WINDOW
def format_reset_in(reset_at, now=None):
    if reset_at is None: return None
    now = now or utc_now()
    total_seconds = max(0, int((reset_at - now).total_seconds()))
    hours, remainder = divmod(total_seconds, 3600)
    minutes = (remainder + 59) // 60
    if hours <= 0: return f"{minutes} min"
    if minutes >= 60:
        hours += 1
        minutes = 0
    if minutes == 0: return f"{hours}h"
    return f"{hours}h {minutes}min"
def build_usage_status(usage, now=None):
    now = now or utc_now()
    if usage is None: return UsageStatus(0, FREE_DAILY_LIMIT, FREE_DAILY_LIMIT, 0, None, None, True)
    ensure_active_window(usage, now)
    used = usage.usage_count
    remaining = max(FREE_DAILY_LIMIT - used, 0)
    reset_at = get_reset_at(usage) if used else None
    return UsageStatus(used, FREE_DAILY_LIMIT, remaining, min(round((used / FREE_DAILY_LIMIT) * 100), 100), reset_at, format_reset_in(reset_at, now), True)
def get_usage_status(usuario=None, session_id=None):
    if is_pro_user(usuario): return UsageStatus(0, None, "Ilimitado", 100, None, None, False)
    if usuario is None and session_id is None: return build_usage_status(None)
    return build_usage_status(get_usage_record(usuario=usuario, session_id=session_id))
def get_limit_message(usage, requested_amount, now=None):
    now = now or utc_now()
    status = build_usage_status(usage, now)
    remaining = status.remaining if isinstance(status.remaining, int) else 0
    reset_text = status.reset_in or "em breve"
    if requested_amount == 1: return f"Voce atingiu o limite de 10 conversoes nesta janela de 24 horas. Tente novamente em {reset_text}."
    return f"Voce tem {remaining} conversoes disponiveis nesta janela de 24 horas, mas este envio precisa de {requested_amount}. Tente novamente em {reset_text}."
def can_use_tool(usuario=None, session_id=None, amount=1):
    if amount < 1: raise ValueError("amount must be greater than zero")
    if is_pro_user(usuario): return True, None, None
    now = utc_now()
    usage = get_usage_record(usuario=usuario, session_id=session_id)
    if usage is None: return True, None, None
    ensure_active_window(usage, now)
    if usage.usage_count + amount > FREE_DAILY_LIMIT: return False, get_limit_message(usage, amount, now), usage
    return True, None, usage
def reserve_tool_usage(usuario=None, session_id=None, amount=1):
    if amount < 1: raise ValueError("amount must be greater than zero")
    if is_pro_user(usuario): return None
    now = utc_now()
    lock_usage_identity(usuario=usuario, session_id=session_id)
    usage = get_or_create_usage_record(usuario=usuario, session_id=session_id, now=now, for_update=True)
    ensure_active_window(usage, now)
    if usage.usage_count + amount > FREE_DAILY_LIMIT: raise PermissionError(get_limit_message(usage, amount, now))
    usage.usage_count += amount
    db.session.flush()
    return usage
def increment_daily_usage(usage):
    if usage is None: raise ValueError("usage cannot be None")
    reserve_tool_usage(usuario=usage.user, session_id=usage.session_id, amount=1)
