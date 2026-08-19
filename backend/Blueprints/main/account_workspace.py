from collections import Counter
from datetime import timedelta
import os

from flask import session
from flask_login import current_user

from models import ConversionJob, Subscription
from Blueprints.services.subscription.access_service import FREE_DAILY_LIMIT, as_utc, get_usage_status, is_pro_user, utc_now


STATUS_LABELS = {
    "queued": "Na fila",
    "processing": "Processando",
    "done": "Concluido",
    "failed": "Falhou",
}

def get_account_workspace():
    if current_user.is_authenticated:
        workspace_identity = get_authenticated_workspace_identity()
    else:
        workspace_identity = get_anonymous_workspace_identity()

    jobs = workspace_identity["jobs_query"].order_by(ConversionJob.created_at.desc()).limit(60).all()
    stats = build_workspace_stats(jobs)
    return {
        **workspace_identity["profile"],
        **stats,
        "status_labels": STATUS_LABELS,
    }

def get_authenticated_workspace_identity():
    usage_status = get_usage_status(usuario=current_user)
    is_pro = is_pro_user(current_user)
    plan = "BoostConvert PRO" if is_pro else "FREE"
    can_cancel_subscription = Subscription.query.filter(
        Subscription.user_id == current_user.id,
        Subscription.provider == "mercado_pago",
        Subscription.provider_subscription_id.isnot(None),
        Subscription.status.in_({"active", "paused", "pending"}),
    ).first() is not None
    return {
        "jobs_query": ConversionJob.query.filter_by(user_id=current_user.id),
        "profile": {
            "display_name": current_user.nome or current_user.email.split("@")[0],
            "email": current_user.email,
            "plan": plan,
            "is_pro": is_pro,
            "can_cancel_subscription": can_cancel_subscription,
            "daily_used": usage_status.used,
            "daily_limit": None if is_pro else FREE_DAILY_LIMIT,
            "daily_remaining": usage_status.remaining if not is_pro else "Ilimitado",
            "daily_percent": usage_status.percent,
            "daily_reset_in": usage_status.reset_in,
            "google_connected": bool(current_user.google_id),
        },
    }

def get_anonymous_workspace_identity():
    session_id = session.get("anon_id")
    usage_status = get_usage_status(session_id=session_id) if session_id else get_usage_status()
    jobs_query = ConversionJob.query.filter_by(session_id=session_id) if session_id else ConversionJob.query.filter(False)
    return {
        "jobs_query": jobs_query,
        "profile": {
            "display_name": "Visitante",
            "email": "Entre para sincronizar seu workspace",
            "plan": "FREE",
            "is_pro": False,
            "can_cancel_subscription": False,
            "daily_used": usage_status.used,
            "daily_limit": FREE_DAILY_LIMIT,
            "daily_remaining": usage_status.remaining,
            "daily_percent": usage_status.percent,
            "daily_reset_in": usage_status.reset_in,
            "google_connected": False,
        },
    }

def build_workspace_stats(jobs):
    total_jobs = len(jobs)
    done_jobs = [job for job in jobs if job.status == "done"]
    last_week_jobs = get_last_week_jobs(jobs)
    return {
        "recent_jobs": jobs[:4],
        "total_jobs": total_jobs,
        "favorite_formats": get_favorite_formats(jobs),
        "last_week_count": len(last_week_jobs),
        "success_rate": round((len(done_jobs) / total_jobs) * 100) if total_jobs else 100,
    }


def get_last_week_jobs(jobs):
    last_week = utc_now() - timedelta(days=7)
    return [job for job in jobs if job.created_at and as_utc(job.created_at) >= last_week]

def get_favorite_formats(jobs):
    output_formats = [
        os.path.splitext(job.output_filename or "")[1].replace(".", "").upper()
        for job in jobs
    ]
    return [fmt for fmt, _ in Counter([fmt for fmt in output_formats if fmt]).most_common(3)] or ["PDF", "WEBP", "DOCX"]
