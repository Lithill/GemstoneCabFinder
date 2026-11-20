"""Offline-only encrypted health vault foundation.

No Flask routes import this module. Nothing accepts or stores tracker answers yet.
Install cryptography before provisioning. Keep secrets outside source control.
"""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken

DEFAULT_PATH = Path.home() / ".gemstonecabfinder-private" / "health_vault.db"


def password_hash(password: str, *, salt: bytes | None = None) -> str:
    """Scrypt password verifier, with per-password random salt."""
    if len(password) < 16:
        raise ValueError("Health-tracker password must be at least 16 characters.")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**15, r=8, p=1, maxmem=64 * 1024 * 1024)
    return "scrypt$32768$8$1$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt, expected = encoded.split("$")
        if scheme != "scrypt" or (n, r, p) != ("32768", "8", "1"):
            return False
        digest = hashlib.scrypt(password.encode("utf-8"), salt=base64.urlsafe_b64decode(salt), n=32768, r=8, p=1, maxmem=64 * 1024 * 1024)
        return hmac.compare_digest(digest, base64.urlsafe_b64decode(expected))
    except (ValueError, TypeError):
        return False


def _key() -> bytes:
    key = os.environ.get("HEALTH_VAULT_KEY", "")
    if not key:
        raise RuntimeError("HEALTH_VAULT_KEY is not configured; vault remains unavailable.")
    try:
        Fernet(key.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Invalid HEALTH_VAULT_KEY.") from exc
    return key.encode("ascii")


def _connect(path: Path):
    path = Path(path).expanduser()
    if not path.exists():
        raise FileNotFoundError("Health vault not provisioned.")
    return sqlite3.connect(path)


def provision(path: Path = DEFAULT_PATH) -> None:
    """Explicit offline setup only; never called by the web app."""
    _key()
    path = Path(path).expanduser()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    if path.exists():
        raise FileExistsError("Refusing to overwrite existing health vault.")
    connection = sqlite3.connect(path)
    try:
        connection.execute("""CREATE TABLE entries (
            day TEXT NOT NULL, question TEXT NOT NULL,
            encrypted_payload BLOB NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(day, question)
        )""")
        connection.execute("CREATE TABLE vault_meta (key TEXT PRIMARY KEY, value BLOB NOT NULL)")
        connection.execute("INSERT INTO vault_meta VALUES ('key_check', ?)", (Fernet(_key()).encrypt(b'health-vault-v1'),))
        connection.commit()
    finally:
        connection.close()
    os.chmod(path, 0o600)


def _verified(conn):
    row = conn.execute("SELECT value FROM vault_meta WHERE key='key_check'").fetchone()
    if not row:
        raise RuntimeError("Vault key check missing.")
    try:
        if Fernet(_key()).decrypt(row[0]) != b"health-vault-v1":
            raise RuntimeError("Unexpected vault key check.")
    except InvalidToken as exc:
        raise RuntimeError("Wrong health vault key.") from exc


def put(day: str, question: str, answer: dict, path: Path = DEFAULT_PATH) -> None:
    """Offline API only. Not connected to web routes or the prototype."""
    from datetime import date
    if date.fromisoformat(day).isoformat() != day or not question or len(question) > 200:
        raise ValueError("Invalid date or question.")
    if not isinstance(answer, dict):
        raise ValueError("Answer must be an object.")
    payload = Fernet(_key()).encrypt(json.dumps(answer, ensure_ascii=False).encode("utf-8"))
    with _connect(path) as conn:
        _verified(conn)
        conn.execute("""INSERT INTO entries (day, question, encrypted_payload, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(day, question) DO UPDATE SET
            encrypted_payload=excluded.encrypted_payload, updated_at=excluded.updated_at""",
            (day, question, payload, datetime.now(timezone.utc).isoformat()))


def get(day: str, question: str, path: Path = DEFAULT_PATH) -> dict | None:
    with _connect(path) as conn:
        _verified(conn)
        row = conn.execute("SELECT encrypted_payload FROM entries WHERE day=? AND question=?", (day, question)).fetchone()
    if not row:
        return None
    return json.loads(Fernet(_key()).decrypt(row[0]))


def encrypted_backup(destination: Path, path: Path = DEFAULT_PATH) -> None:
    """Produce a separately encrypted, portable SQLite snapshot; never plaintext backup."""
    destination = Path(destination).expanduser()
    if destination.exists():
        raise FileExistsError("Refusing to overwrite backup.")
    with _connect(path) as source:
        _verified(source)
        snapshot = sqlite3.connect(":memory:")
        try:
            source.backup(snapshot)
            raw = snapshot.serialize()
        finally:
            snapshot.close()
    encrypted = Fernet(_key()).encrypt(raw)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(encrypted)


def restore_backup(source: Path, destination: Path) -> None:
    """Offline restore to a NEW file only. Verify backup and key before writing."""
    source, destination = Path(source).expanduser(), Path(destination).expanduser()
    raw = Fernet(_key()).decrypt(source.read_bytes())
    check = sqlite3.connect(":memory:")
    try:
        check.deserialize(raw)
        _verified(check)
        if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Backup integrity check failed.")
    finally:
        check.close()
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(raw)
