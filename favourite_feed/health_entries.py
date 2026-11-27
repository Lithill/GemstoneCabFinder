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


def delete_validated(day: str, question: str, *, path: Path) -> bool:
    """Delete exactly one known entry from an existing offline vault.

    Validate both identifiers before accessing the vault. This is logical
    deletion, not guaranteed erasure from journals, snapshots or backups.
    """
    _validate_identity(day, question)
    return health_vault.delete(day, question, path)


def _validate_identity(day: str, question: str) -> None:
    from datetime import date
    from favourite_feed.health_answers import QUESTIONS
    if not isinstance(question, str) or question not in QUESTIONS:
        raise ValueError("Unknown symptom question.")
    if not isinstance(day, str):
        raise ValueError("Invalid entry date.")
    try:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError
    except ValueError as exc:
        raise ValueError("Invalid entry date.") from exc


def get_validated(day: str, question: str, *, path: Path) -> dict | None:
    """Read a known question and reject invalid or damaged stored answers."""
    _validate_identity(day, question)
    answer = health_vault.get(day, question, path)
    if answer is None:
        return None
    return validate_entry(day, question, answer)["answer"]


def get_many_validated(day: str, questions, *, path: Path) -> dict:
    """Read known questions together, validating every returned answer."""
    questions = tuple(questions)
    for question in questions:
        _validate_identity(day, question)
    answers = health_vault.get_many(day, questions, path)
    return {question: validate_entry(day, question, answer)["answer"]
            for question, answer in answers.items()}
