"""Offline-only atomic multi-question check-ins for a provisioned health vault.

Never imported by Flask routes. No vault provisioning or web saving.
"""
from contextlib import closing
from datetime import date
import json
from pathlib import Path

from cryptography.fernet import Fernet

from favourite_feed.health_answers import QUESTIONS, validate_entry
from favourite_feed import health_vault


def put_checkin(day: str, answers: dict, *, path: Path) -> int:
    """Validate all answers, then upsert them in one SQLite transaction.

    Empty dict is a no-op. A failure never commits a partial check-in.
    """
    if not isinstance(answers, dict) or len(answers) > len(QUESTIONS):
        raise ValueError("Check-in must be a question-to-answer mapping.")
    if not isinstance(day, str):
        raise ValueError("Invalid check-in date.")
    try:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError
    except ValueError as exc:
        raise ValueError("Invalid check-in date.") from exc
    # Validate every submitted answer before any database changes are attempted.
    validated = [validate_entry(day, question, answer) for question, answer in answers.items()]
    if not validated:
        # A no-op still requires a provisioned vault and the correct key.
        with closing(health_vault._connect(path)) as conn:
            health_vault._verified(conn)
        return 0
    # Prepare encrypted records in memory before opening the write transaction.
    cipher = Fernet(health_vault._key())
    prepared = []
    for entry in validated:
        raw = json.dumps(entry, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(raw) > 16 * 1024:
            raise ValueError("Health entry exceeds size limit.")
        prepared.append((health_vault._entry_id(entry["day"], entry["question"]), cipher.encrypt(raw)))
    # Commit all prepared answers together or roll back on failure. Unsubmitted questions remain unchanged.
    with closing(health_vault._connect(path)) as conn, conn:
        health_vault._verified(conn)
        conn.executemany(
            """INSERT INTO entries (entry_id, encrypted_payload) VALUES (?, ?)
            ON CONFLICT(entry_id) DO UPDATE SET encrypted_payload=excluded.encrypted_payload""",
            prepared,
        )
    return len(prepared)
