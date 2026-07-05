from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from time import monotonic

from flask import Flask, Response, abort, current_app, request, session
from werkzeug.middleware.proxy_fix import ProxyFix


CSRF_FIELD_NAME = "_csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_SESSION_KEY = "_boost_csrf_token"
CSRF_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_EXEMPT_ENDPOINTS = {
    "webhook.webhook",
    "webhook.receive_mercado_pago_webhook",
}


@dataclass(frozen=True)
class RateLimitRule:
    max_requests: int
    window_seconds: int


RATE_LIMIT_HITS: dict[str, list[float]] = {}
AUTH_RATE_LIMITS = {
    "auth.login": RateLimitRule(5, 300),
    "auth.registrar": RateLimitRule(5, 300),
}
ENDPOINT_RATE_LIMITS = {
    "checkout.checkout_credit_subscription": RateLimitRule(10, 60),
    "checkout.checkout_pix": RateLimitRule(10, 60),
    "checkout.checkout_debit": RateLimitRule(10, 60),
    "home.conversion_download": RateLimitRule(120, 60),
    "home.conversion_batch_download": RateLimitRule(60, 60),
}
CONVERSION_RATE_LIMIT = RateLimitRule(30, 60)


def init_security(app: Flask) -> None:
    """Attach security middleware to the Flask app.

    Example: init_security(app)
    """
    configure_proxy_fix(app)
    app.context_processor(inject_csrf_helpers)
    app.before_request(mark_session_permanent)
    app.before_request(enforce_csrf_token)
    app.before_request(enforce_rate_limit)
    app.after_request(apply_security_headers)


def configure_proxy_fix(app: Flask) -> None:
    """Trust reverse-proxy headers only when explicitly configured.

    Example: configure_proxy_fix(app)
    """
    if not app.config.get("TRUST_PROXY_HEADERS"):
        return
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)


def inject_csrf_helpers() -> dict[str, object]:
    return {"csrf_token": get_csrf_token, "csrf_field_name": CSRF_FIELD_NAME}


def get_csrf_token() -> str:
    """Return the per-session CSRF token used by POST forms.

    Example: token = get_csrf_token()
    """
    token = session.get(CSRF_SESSION_KEY)
    if isinstance(token, str) and len(token) >= 32:
        return token
    token = secrets.token_urlsafe(32)
    session[CSRF_SESSION_KEY] = token
    return token


def mark_session_permanent() -> None:
    if current_app.config.get("SESSION_PERMANENT", True):
        session.permanent = True


def enforce_csrf_token() -> None:
    if not is_csrf_required():
        return
    expected_token = session.get(CSRF_SESSION_KEY, "")
    submitted_token = get_submitted_csrf_token()
    if not is_valid_csrf_pair(expected_token, submitted_token):
        abort(400)


def is_csrf_required() -> bool:
    if not current_app.config.get("CSRF_ENABLED", True):
        return False
    if request.method not in CSRF_METHODS:
        return False
    return request.endpoint not in CSRF_EXEMPT_ENDPOINTS


def get_submitted_csrf_token() -> str:
    form_token = request.form.get(CSRF_FIELD_NAME, "")
    if form_token:
        return form_token
    return request.headers.get(CSRF_HEADER_NAME, "")


def is_valid_csrf_pair(expected_token: object, submitted_token: str) -> bool:
    if not isinstance(expected_token, str) or not submitted_token:
        return False
    return hmac.compare_digest(expected_token, submitted_token)


def enforce_rate_limit() -> None:
    rule = get_rate_limit_rule()
    if rule is None or not current_app.config.get("RATE_LIMIT_ENABLED", True):
        return
    hits = get_recent_rate_limit_hits(get_rate_limit_key(), rule.window_seconds)
    if len(hits) >= rule.max_requests:
        abort(429)
    hits.append(monotonic())


def get_rate_limit_rule() -> RateLimitRule | None:
    if request.method == "POST" and request.endpoint in AUTH_RATE_LIMITS:
        return AUTH_RATE_LIMITS[request.endpoint]
    if request.method == "POST" and request.path.startswith("/convert/"):
        return CONVERSION_RATE_LIMIT
    return ENDPOINT_RATE_LIMITS.get(request.endpoint or "")


def get_rate_limit_key() -> str:
    client_id = request.remote_addr or "unknown"
    endpoint_id = request.endpoint or request.path
    return f"{client_id}:{endpoint_id}"


def get_recent_rate_limit_hits(key: str, window_seconds: int) -> list[float]:
    now = monotonic()
    cutoff = now - window_seconds
    hits = [hit for hit in RATE_LIMIT_HITS.get(key, []) if hit >= cutoff]
    RATE_LIMIT_HITS[key] = hits
    return hits


def clear_rate_limit_state() -> None:
    """Clear in-memory rate-limit buckets for tests.

    Example: clear_rate_limit_state()
    """
    RATE_LIMIT_HITS.clear()


def apply_security_headers(response: Response) -> Response:
    response.headers.setdefault("Content-Security-Policy", build_content_security_policy())
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if current_app.config.get("FORCE_HTTPS"):
        response.headers.setdefault("Strict-Transport-Security", build_hsts_header())
    return response


def build_content_security_policy() -> str:
    directives = [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' https://unpkg.com https://sdk.mercadopago.com",
        "style-src 'self' 'unsafe-inline' https://api.fontshare.com https://fonts.googleapis.com",
        "img-src 'self' data:",
        "font-src 'self' data: https://api.fontshare.com https://cdn.fontshare.com https://fonts.gstatic.com",
        "connect-src 'self' https://api.mercadopago.com https://*.mercadopago.com https://*.mercadopago.com.br",
        "frame-src https://*.mercadopago.com https://*.mercadopago.com.br",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
    return "; ".join(directives)


def build_hsts_header() -> str:
    max_age = int(current_app.config.get("HSTS_MAX_AGE_SECONDS", 31536000))
    return f"max-age={max_age}; includeSubDomains"
