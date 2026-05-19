from datetime import datetime
from zoneinfo import ZoneInfo

from extensions import db
from models import DailyUsage
from Blueprints.services.subscription.subscription_service import has_active_pro_subscription

APP_TZ = ZoneInfo("America/Sao_Paulo")
FREE_DAILY_LIMIT = 12

def get_today_date():
    return datetime.now(APP_TZ).date()

def get_daily_usage_record(usuario=None, session_id=None):
    today = get_today_date()

    query = DailyUsage.query.filter(DailyUsage.usage_date == today)

    if usuario is not None: query = query.filter(DailyUsage.user_id == usuario.id)
    else:
        if session_id is None:
            raise ValueError("session_id is required for anonymous users")

        query = query.filter(DailyUsage.session_id == session_id)

    return query.first()

def create_daily_usage_record(usuario=None, session_id=None):
    usage = DailyUsage(
         user_id=usuario.id if usuario is not None else None
        ,session_id=session_id if usuario is None else None
        ,usage_date=get_today_date()
        ,usage_count=0
    )

    db.session.add(usage)
    db.session.commit()
    return usage

def get_or_create_daily_usage(usuario=None, session_id=None):
    usage = get_daily_usage_record(usuario=usuario, session_id=session_id)

    if usage is not None: return usage

    return create_daily_usage_record(usuario=usuario, session_id=session_id)

def is_pro_user(usuario):
    return has_active_pro_subscription(usuario)

def can_use_tool(usuario=None, session_id=None):
    if is_pro_user(usuario): return True, None, None

    usage = get_or_create_daily_usage(usuario=usuario, session_id=session_id)

    if usage.usage_count >= FREE_DAILY_LIMIT:
        return False, "Voce atingiu o limite diario de ferramentas!", usage

    return True, None, usage

def increment_daily_usage(usage):
    if usage is None:
        raise ValueError("usage cannot be None")

    usage.usage_count += 1
    db.session.commit()
