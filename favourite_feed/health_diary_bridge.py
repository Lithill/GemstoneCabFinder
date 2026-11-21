"""Disabled-by-default bridge from the prototype diary to encrypted offline check-ins.

This module registers no routes and is not imported by the web app.
It accepts the current browser diary *shape*, not arbitrary health JSON.
No notes are retained, transmitted or written.
"""
import math
from pathlib import Path

from favourite_feed.health_answers import QUESTIONS, validate_entry
from favourite_feed.health_checkins import put_checkin
from favourite_feed.health_entries import get_validated


def _convert(entry):
    if not isinstance(entry, dict) or set(entry) != {"name", "answer", "extras", "notes"}:
        raise ValueError("Unexpected prototype diary entry.")
    question, raw, extras, notes = (entry[k] for k in ("name", "answer", "extras", "notes"))
    if not isinstance(question, str) or question not in QUESTIONS:
        raise ValueError("Unknown symptom question.")
    if not isinstance(raw, str) or not raw.strip() or raw != raw.strip():
        raise ValueError("Invalid prototype answer.")
    if not isinstance(extras, list) or len(extras) > 4 or not isinstance(notes, str):
        raise ValueError("Invalid prototype entry details.")
    if len(notes) > 4096:
        raise ValueError("Prototype note is too long.")
    result = {"answer": raw}
    for extra in extras:
        if not isinstance(extra, str) or ": " not in extra:
            raise ValueError("Malformed prototype extra.")
        key, value = extra.split(": ", 1)
        if key not in {"flow", "detail", "hours", "unit"} or not value or key in result:
            raise ValueError("Invalid or duplicate prototype extra.")
        if key == "hours":
            try:
                value = float(value)
            except ValueError as exc:
                raise ValueError("Invalid sleep hours.") from exc
            if not math.isfinite(value):
                raise ValueError("Invalid sleep hours.")
        result[key] = value
    if QUESTIONS[question] == "weight":
        try:
            result["answer"] = float(raw)
        except ValueError as exc:
            raise ValueError("Invalid weight.") from exc
        if not math.isfinite(result["answer"]):
            raise ValueError("Invalid weight.")
    return question, result


def prepare_diary(day: str, diary: list) -> dict:
    """Convert and validate a complete guided/quick-entry diary, without writing."""
    if not isinstance(diary, list) or len(diary) > len(QUESTIONS):
        raise ValueError("Invalid prototype diary.")
    answers = {}
    for item in diary:
        question, answer = _convert(item)
        if question in answers:
            raise ValueError("Duplicate symptom question.")
        answers[question] = validate_entry(day, question, answer)["answer"]
    # Validate the date even when the diary is empty.
    from datetime import date
    if not isinstance(day, str):
        raise ValueError("Invalid check-in date.")
    try:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError
    except ValueError as exc:
        raise ValueError("Invalid check-in date.") from exc
    return answers


def save_diary_offline(day: str, diary: list, *, path: Path) -> int:
    """Explicit offline invocation only; never called from a Flask route."""
    return put_checkin(day, prepare_diary(day, diary), path=path)


def read_diary_offline(day: str, *, path: Path) -> list:
    """Read the same shape used by the prototype, without restoring notes."""
    prepare_diary(day, [])
    diary = []
    for question in QUESTIONS:
        answer = get_validated(day, question, path=path)
        if answer is None:
            continue
        extras = [f"{key}: {answer[key]}" for key in ("flow", "detail", "hours", "unit") if key in answer]
        diary.append({"name": question, "answer": str(answer["answer"]), "extras": extras, "notes": ""})
    return diary
