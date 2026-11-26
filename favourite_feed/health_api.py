"""Opt-in private health API for isolated staging only.

Requires BOTH preview and storage staging switches. Never provisions a vault.
Do not enable on production before privacy/security review and explicit approval.
"""
import os
from pathlib import Path

from flask import Blueprint, abort, jsonify, request

from favourite_feed.health_auth import _valid_session, health_csrf_required
from favourite_feed.health_diary_bridge import read_diary_offline, save_diary_offline
from favourite_feed.health_entries import delete_validated

health_api = Blueprint("health_api", __name__, url_prefix="/private-health-api")


def _vault_path():
    configured = os.environ.get("HEALTH_STAGING_VAULT_PATH", "")
    if not configured:
        abort(503)
    path = Path(configured).expanduser()
    # Staging vaults must live outside the repository and use a distinct name.
    # Do not allow configuration to point at the production gemstone DB or at
    # the default health vault reserved for future approved production use.
    from favourite_feed.health_vault import DEFAULT_PATH
    if (path.name in {"favourite_feed.db", "health_vault.db"}
            or path.resolve() == DEFAULT_PATH.resolve()
            or path.is_symlink()):
        abort(503)
    return path


@health_api.before_request
def require_private_session():
    if os.environ.get("HEALTH_STAGING_STORAGE_ENABLED") != "1":
        abort(404)
    if not _valid_session():
        abort(401)
    if request.method != "GET":
        health_csrf_required()
        if request.content_length is None or request.content_length > 65536:
            abort(413)
        if not request.is_json:
            abort(415)


@health_api.after_request
def private_headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@health_api.get("/session")
def session():
    current = _valid_session()
    return jsonify(csrf=current["csrf"])


@health_api.get("/checkin/<day>")
def read_checkin(day):
    try:
        entries = read_diary_offline(day, path=_vault_path())
    except ValueError:
        abort(400)
    return jsonify(day=day, entries=entries)


@health_api.post("/checkin/<day>")
def save_checkin(day):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != {"entries"}:
        abort(400)
    try:
        count = save_diary_offline(day, payload["entries"], path=_vault_path())
    except (ValueError, TypeError):
        abort(400)
    return jsonify(saved=count)


@health_api.post("/delete/<day>")
def delete_checkin_entry(day):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != {"question"}:
        abort(400)
    try:
        deleted = delete_validated(day, payload["question"], path=_vault_path())
    except ValueError:
        abort(400)
    return jsonify(deleted=deleted)


def register_staging_api(app):
    """Registration requires an explicit second switch; never called by default."""
    if os.environ.get("HEALTH_STAGING_STORAGE_ENABLED") != "1":
        return
    app.register_blueprint(health_api)
