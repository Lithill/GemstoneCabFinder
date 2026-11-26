"""Opt-in private health API for isolated staging only.

Requires BOTH preview and storage staging switches. Never provisions a vault.
Do not enable on production before privacy/security review and explicit approval.
"""
import os
from pathlib import Path
from datetime import date
from calendar import monthrange
from favourite_feed.health_answers import QUESTIONS

from flask import Blueprint, abort, jsonify, request, current_app

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


def _backup_after_write(path):
    if os.environ.get("HEALTH_AUTO_BACKUP_ENABLED") != "1":
        return None
    try:
        from scripts.health_daily_backup import rotate
        rotate(path, path.parent / (path.name + ".backups"), refresh=True)
        return True
    except Exception:
        current_app.logger.error("Health diary saved but encrypted backup failed")
        return False


@health_api.route("/factors/<day>", methods=["GET", "POST"])
def factors(day):
    from favourite_feed.health_vault import get, put, delete
    try:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError
    except ValueError:
        abort(400)
    path = _vault_path()
    question = "lifestyle-factors-v1"
    if request.method == "GET":
        return jsonify(items=(get(day, question, path=path) or {}).get("items", []))
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != {"items"}:
        abort(400)
    items = payload["items"]
    if not isinstance(items, list) or len(items) > 20:
        abort(400)
    for item in items:
        if not isinstance(item, dict) or set(item) != {"category", "name", "value"}:
            abort(400)
        if item["category"] not in ("Exercise", "Medication", "Supplement", "Stress", "Caffeine", "Alcohol", "Diet", "Other"):
            abort(400)
        if any(not isinstance(item[k], str) or not item[k].strip() or len(item[k]) > 100 for k in ("name", "value")):
            abort(400)
    try:
        if items:
            put(day, question, {"items": items}, path=path)
        else:
            delete(day, question, path=path)
    except ValueError:
        abort(400)
    return jsonify(saved=len(items), backup_ok=_backup_after_write(path))


@health_api.route("/ongoing", methods=["GET", "POST"])
def ongoing():
    from favourite_feed.health_ongoing import validate, KEY_DAY, KEY_QUESTION
    from favourite_feed.health_vault import get, put, delete
    path = _vault_path()
    if request.method == "GET":
        return jsonify(items=(get(KEY_DAY, KEY_QUESTION, path=path) or {}).get("items", []))
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != {"items"}:
        abort(400)
    try:
        items = validate(payload["items"])
        if items:
            put(KEY_DAY, KEY_QUESTION, {"items": items}, path=path)
        else:
            delete(KEY_DAY, KEY_QUESTION, path=path)
    except (ValueError, TypeError):
        abort(400)
    return jsonify(saved=len(items), backup_ok=_backup_after_write(path))


@health_api.get("/impact/<day>/<int:window>")
def impact(day, window):
    from datetime import timedelta
    from favourite_feed.health_impact import compare
    from favourite_feed.health_ongoing import KEY_DAY, KEY_QUESTION
    from favourite_feed.health_vault import get
    try:
        change = date.fromisoformat(day)
        if change.isoformat() != day or window not in (7, 14, 30):
            raise ValueError
        start, end = change - timedelta(days=window), change + timedelta(days=window)
    except (ValueError, OverflowError):
        abort(400)
    path = _vault_path()
    items = (get(KEY_DAY, KEY_QUESTION, path=path) or {}).get("items", [])
    events = [{"name": item["name"], **event} for item in items for event in item["history"]
              if start.isoformat() <= event["day"] <= end.isoformat()]
    rows = compare(change, window, date.today(), lambda d: read_diary_offline(d, path=path))
    return jsonify(rows=rows, events=events)


@health_api.route("/exercise/<day>", methods=["GET", "POST"])
def exercise(day):
    from favourite_feed.health_exercise import KEY, validate
    from favourite_feed.health_vault import get, put, delete
    try:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError
    except ValueError:
        abort(400)
    path = _vault_path()
    if request.method == "GET":
        return jsonify(get(day, KEY, path=path) or {"rest": False, "sessions": []})
    try:
        log = validate(request.get_json(silent=True))
        if log["rest"] or log["sessions"]:
            put(day, KEY, log, path=path)
        else:
            delete(day, KEY, path=path)
    except (ValueError, TypeError):
        abort(400)
    return jsonify(backup_ok=_backup_after_write(path))


@health_api.get("/exercise-impact/<int:days>/<int:lag>")
def exercise_impact(days, lag):
    from favourite_feed.health_exercise import KEY, compare_exercise
    from favourite_feed.health_vault import get
    if days not in (30, 60, 90) or lag not in (0, 1, 2, 3):
        abort(400)
    path = _vault_path()
    return jsonify(compare_exercise(date.today(), days, lag,
        lambda d: get(d, KEY, path=path),
        lambda d: read_diary_offline(d, path=path)))


@health_api.get("/personal-insights")
def personal_insights():
    from favourite_feed.health_personal_insights import summarize
    from favourite_feed.health_ongoing import KEY_DAY, KEY_QUESTION
    from favourite_feed.health_exercise import KEY
    from favourite_feed.health_vault import get
    path = _vault_path()
    items = (get(KEY_DAY, KEY_QUESTION, path=path) or {}).get("items", [])
    return jsonify(summarize(date.today(), items,
        lambda d: read_diary_offline(d, path=path),
        lambda d: get(d, KEY, path=path)))


@health_api.get("/session")
def session():
    current = _valid_session()
    return jsonify(csrf=current["csrf"])


@health_api.get("/month/<month>")
def read_month(month):
    try:
        first = date.fromisoformat(month + "-01")
        if first.strftime("%Y-%m") != month:
            raise ValueError
    except ValueError:
        abort(400)
    path = _vault_path()
    days = {}
    for n in range(1, monthrange(first.year, first.month)[1] + 1):
        day = first.replace(day=n).isoformat()
        entries = read_diary_offline(day, path=path)
        if entries:
            days[day] = {"count": len(entries), "severity": {
                e["name"]: e["answer"] for e in entries
                if QUESTIONS[e["name"]] in {"severity", "sleep"}
            }}
    return jsonify(days=days, symptoms=[q for q, kind in QUESTIONS.items()
                                      if kind in {"severity", "sleep"}])


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
    return jsonify(saved=count, backup_ok=_backup_after_write(_vault_path()))


@health_api.post("/delete/<day>")
def delete_checkin_entry(day):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != {"question"}:
        abort(400)
    try:
        deleted = delete_validated(day, payload["question"], path=_vault_path())
    except ValueError:
        abort(400)
    return jsonify(deleted=deleted, backup_ok=_backup_after_write(_vault_path()))


def register_staging_api(app):
    """Registration requires an explicit second switch; never called by default."""
    if os.environ.get("HEALTH_STAGING_STORAGE_ENABLED") != "1":
        return
    app.register_blueprint(health_api)
