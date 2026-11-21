"""Offline-only validated health entry operations.

NOT imported by Flask routes. This module cannot provision a vault and does
not enable browser saving. Use only with an explicitly provisioned offline
vault; tests use synthetic answers and temporary databases.
"""
from pathlib import Path

from favourite_feed.health_answers import validate_entry
from favourite_feed import health_vault


def put_validated(day: str, question: str, answer: dict, *, path: Path) -> None:
    """Validate an entire entry before modifying an existing encrypted vault."""
    entry = validate_entry(day, question, answer)
    health_vault.put(entry["day"], entry["question"], entry["answer"], path)


def get_validated(day: str, question: str, *, path: Path) -> dict | None:
    """Read a known question and reject invalid or damaged stored answers."""
    if not isinstance(question, str) or question not in health_vault_questions():
        raise ValueError("Unknown symptom question.")
    # Validation is also applied to the date, even for missing records.
    from datetime import date
    if not isinstance(day, str):
        raise ValueError("Invalid entry date.")
    try:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError
    except ValueError as exc:
        raise ValueError("Invalid entry date.") from exc
    answer = health_vault.get(day, question, path)
    if answer is None:
        return None
    return validate_entry(day, question, answer)["answer"]


def health_vault_questions():
    from favourite_feed.health_answers import QUESTIONS
    return QUESTIONS
