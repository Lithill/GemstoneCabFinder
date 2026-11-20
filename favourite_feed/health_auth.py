"""Isolated health login blueprint. NOT registered in the live Flask app.

The existing symptom-tracker preview is unaffected. Health data routes are
not implemented. Registration requires a separate security review.
"""
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import sqlite3
import time
from functools import wraps

from flask import Blueprint, abort, make_response, redirect, render_template_string, request, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from favourite_feed.health_vault import verify_password

health_auth = Blueprint("health_auth", __name__, url_prefix="/health-auth")
COOKIE = "__Host-health_session"
SESSION_IDLE_SECONDS = 20 * 60
MAX_FAILURES = 5
LOCK_SECONDS = 15 * 60
RATE_DB = Path.home() / ".gemstonecabfinder-private" / "health_login_limits.db"

LOGIN_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Private tracker login</title></head><body>
<main><h1>Private health tracker</h1>
<p>Login only. Health-data saving is not enabled.</p>
{% if error %}<p role="alert">Login unsuccessful. Please check your password or try later.</p>{% endif %}
<form method="post" action="{{ url_for('health_auth.login') }}">
<input type="hidden" name="csrf" value="{{ csrf }}">
<label for="password">Tracker password</label>
<input id="password" name="password" type="password" autocomplete="current-password" required>
<button type="submit">Sign in</button></form></main></body></html>"""


def _secret():
    secret = os.environ.get("HEALTH_SESSION_SECRET", "")
    if len(secret) < 43:
        raise RuntimeError("HEALTH_SESSION_SECRET must be a separate, random 32+ byte secret.")
    return secret


def _signer(salt):
    return URLSafeTimedSerializer(_secret(), salt=salt)


def credentials_ready():
    return bool(os.environ.get("HEALTH_PASSWORD_HASH") and os.environ.get("HEALTH_VAULT_KEY") and os.environ.get("HEALTH_SESSION_SECRET"))


def check_password(candidate):
    verifier = os.environ.get("HEALTH_PASSWORD_HASH", "")
    return bool(verifier) and verify_password(candidate, verifier)


def _identity():
    # Only trust the actual connection address; do not trust forwarded headers.
    address = request.remote_addr or "unknown"
    return hmac.new(_secret().encode(), address.encode(), hashlib.sha256).hexdigest()


def _rate_connection():
    RATE_DB.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(RATE_DB.parent, 0o700)
    conn = sqlite3.connect(RATE_DB, timeout=10)
    conn.execute("CREATE TABLE IF NOT EXISTS attempts (identity TEXT PRIMARY KEY, failures INTEGER NOT NULL, locked_until INTEGER NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS revoked_sessions (nonce_hash TEXT PRIMARY KEY, expires_at INTEGER NOT NULL)")
    os.chmod(RATE_DB, 0o600)
    return conn


def _locked(identity, now):
    with _rate_connection() as conn:
        row = conn.execute("SELECT failures, locked_until FROM attempts WHERE identity=?", (identity,)).fetchone()
        return bool(row and row[1] > now)


def _failure(identity, now):
    with _rate_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT failures, locked_until FROM attempts WHERE identity=?", (identity,)).fetchone()
        if row and row[1] > now:
            return
        failures = (row[0] if row and row[1] == 0 else 0) + 1
        locked_until = now + LOCK_SECONDS if failures >= MAX_FAILURES else 0
        conn.execute("INSERT INTO attempts VALUES (?, ?, ?) ON CONFLICT(identity) DO UPDATE SET failures=excluded.failures, locked_until=excluded.locked_until", (identity, failures, locked_until))


def _clear_failures(identity):
    with _rate_connection() as conn:
        conn.execute("DELETE FROM attempts WHERE identity=?", (identity,))


def _cookie(response, token=None, *, clear=False):
    if token:
        response.set_cookie(COOKIE, token, secure=True, httponly=True, samesite="Strict", path="/")
    elif clear:
        response.delete_cookie(COOKIE, secure=True, httponly=True, samesite="Strict", path="/")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _nonce_hash(nonce):
    return hmac.new(_secret().encode(), nonce.encode(), hashlib.sha256).hexdigest()


def _revoke(nonce):
    with _rate_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO revoked_sessions VALUES (?, ?)", (_nonce_hash(nonce), int(time.time()) + SESSION_IDLE_SECONDS))
        conn.execute("DELETE FROM revoked_sessions WHERE expires_at < ?", (int(time.time()),))


def _valid_session():
    token = request.cookies.get(COOKIE, "")
    if not token:
        return None
    try:
        data = _signer("health-session-v1").loads(token, max_age=SESSION_IDLE_SECONDS)
        if data.get("auth") is True and isinstance(data.get("csrf"), str) and isinstance(data.get("nonce"), str):
            with _rate_connection() as conn:
                revoked = conn.execute("SELECT 1 FROM revoked_sessions WHERE nonce_hash=?", (_nonce_hash(data["nonce"]),)).fetchone()
            if not revoked:
                return data
    except (BadSignature, SignatureExpired, ValueError, TypeError):
        pass
    return None


def require_health_login(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not _valid_session():
            return redirect(url_for("health_auth.login"), code=303)
        return view(*args, **kwargs)
    return wrapped


@health_auth.route("/login", methods=["GET", "POST"])
def login():
    if not credentials_ready():
        abort(503)
    identity = _identity()
    now = int(time.time())
    if request.method == "GET":
        csrf = _signer("health-login-csrf-v1").dumps({"nonce": secrets.token_urlsafe(24)})
        response = make_response(render_template_string(LOGIN_HTML, csrf=csrf, error=False))
        response.set_cookie("__Host-health_login_csrf", csrf, secure=True, httponly=True, samesite="Strict", path="/", max_age=600)
        return _cookie(response)
    if request.content_length is not None and request.content_length > 4096:
        abort(413)
    supplied = request.form.get("csrf", "")
    cookie_csrf = request.cookies.get("__Host-health_login_csrf", "")
    try:
        _signer("health-login-csrf-v1").loads(supplied, max_age=600)
        valid_csrf = bool(cookie_csrf) and hmac.compare_digest(supplied, cookie_csrf)
    except (BadSignature, SignatureExpired):
        valid_csrf = False
    if not valid_csrf:
        abort(400)
    if _locked(identity, now):
        response = make_response(render_template_string(LOGIN_HTML, csrf=supplied, error=True), 429)
        response.headers["Retry-After"] = str(LOCK_SECONDS)
        return _cookie(response)
    password = request.form.get("password", "")
    if not check_password(password):
        _failure(identity, now)
        return _cookie(make_response(render_template_string(LOGIN_HTML, csrf=supplied, error=True), 401))
    _clear_failures(identity)
    token = _signer("health-session-v1").dumps({"auth": True, "csrf": secrets.token_urlsafe(32), "nonce": secrets.token_urlsafe(32)})
    response = make_response(redirect(url_for("health_auth.home"), code=303))
    response.delete_cookie("__Host-health_login_csrf", secure=True, httponly=True, samesite="Strict", path="/")
    return _cookie(response, token)


@health_auth.get("/")
@require_health_login
def home():
    current = _valid_session()
    html = """<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Private tracker</title></head><body>
    <h1>Private tracker login verified</h1>
    <p>Health-data collection is not enabled.</p>
    <form method="post" action="{{ url_for('health_auth.logout') }}">
    <input type="hidden" name="csrf" value="{{ csrf }}">
    <button type="submit">Sign out</button></form></body></html>"""
    return _cookie(make_response(render_template_string(html, csrf=current["csrf"])))


@health_auth.post("/logout")
@require_health_login
def logout():
    current = _valid_session()
    supplied = request.form.get("csrf", "")
    if not current or not hmac.compare_digest(supplied, current["csrf"]):
        abort(400)
    _revoke(current["nonce"])
    return _cookie(make_response(redirect(url_for("health_auth.login"), code=303)), clear=True)


def health_csrf_required():
    """For future write endpoints: verify a session-bound CSRF token."""
    current = _valid_session()
    if not current or not hmac.compare_digest(request.headers.get("X-Health-CSRF", ""), current["csrf"]):
        abort(403)
