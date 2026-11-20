"""Separate health-tracker authentication primitives; NOT wired into Flask routes.

No health login or collection is enabled by importing this module.
"""
import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import abort, redirect, request, session, url_for
from favourite_feed.health_vault import verify_password

SESSION_KEY = "health_authenticated_at"
IDLE_MINUTES = 20


def credentials_ready() -> bool:
    return bool(os.environ.get("HEALTH_PASSWORD_HASH") and os.environ.get("HEALTH_SESSION_SECRET") and os.environ.get("HEALTH_VAULT_KEY"))


def check_password(candidate: str) -> bool:
    encoded = os.environ.get("HEALTH_PASSWORD_HASH", "")
    return bool(encoded) and verify_password(candidate, encoded)


def require_health_login(view):
    """Future route decorator; do not use until session, CSRF and rate limits are complete."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        # Fail closed until full login integration has been reviewed.
        abort(503)
    return wrapped
