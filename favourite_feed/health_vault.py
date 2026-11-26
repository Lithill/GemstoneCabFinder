"""Offline-only encrypted health vault foundation.

No Flask routes import this module. Nothing accepts or stores tracker answers yet.
Install cryptography before provisioning. Keep secrets outside source control.
"""
import base64
import binascii
from contextlib import closing
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3

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
    except (ValueError, TypeError, binascii.Error):
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
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Health vault path must be a regular file, not a symlink.")
    return sqlite3.connect(path)


def provision(path: Path = DEFAULT_PATH) -> None:
    """Explicit offline setup only; never called by the web app."""
    _key()
    path = Path(path).expanduser()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    if path.exists() or path.is_symlink():
        raise FileExistsError("Refusing to overwrite existing health vault.")
    # Reserve the file atomically with private permissions before SQLite writes.
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        connection = sqlite3.connect(path)
        try:
            connection.execute("""CREATE TABLE entries (
                entry_id TEXT PRIMARY KEY,
                encrypted_payload BLOB NOT NULL
            )""")
            connection.execute("CREATE TABLE vault_meta (key TEXT PRIMARY KEY, value BLOB NOT NULL)")
            connection.execute("INSERT INTO vault_meta VALUES ('key_check', ?)", (Fernet(_key()).encrypt(b'health-vault-v1'),))
            connection.commit()
        finally:
            connection.close()
    except Exception:
        # A failed first-time setup must not leave a half-provisioned vault.
        path.unlink()
        raise


def _verified(conn):
    # Reject legacy or damaged schemas before any reads, writes, or restores.
    # In particular, legacy vaults had plaintext day/question columns.
    columns = [row[1] for row in conn.execute("PRAGMA table_info(entries)")]
    if columns != ["entry_id", "encrypted_payload"]:
        raise RuntimeError("Unsupported health vault schema; offline migration required.")
    row = conn.execute("SELECT value FROM vault_meta WHERE key='key_check'").fetchone()
    if not row:
        raise RuntimeError("Vault key check missing.")
    try:
        if Fernet(_key()).decrypt(row[0]) != b"health-vault-v1":
            raise RuntimeError("Unexpected vault key check.")
    except InvalidToken as exc:
        raise RuntimeError("Wrong health vault key.") from exc


def _entry_id(day: str, question: str) -> str:
    """Deterministic secret lookup without exposing dates or symptom names."""
    return hmac.new(_key(), json.dumps([day, question], separators=(",", ":"), ensure_ascii=False).encode("utf-8"), hashlib.sha256).hexdigest()


def put(day: str, question: str, answer: dict, path: Path = DEFAULT_PATH) -> None:
    """Offline API only. Not connected to web routes or the prototype."""
    from datetime import date
    if date.fromisoformat(day).isoformat() != day or not question or len(question) > 200:
        raise ValueError("Invalid date or question.")
    if not isinstance(answer, dict):
        raise ValueError("Answer must be an object.")
    try:
        serialized = json.dumps(
            {"day": day, "question": question, "answer": answer},
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("Answer must contain valid JSON data.") from exc
    if len(serialized) > 16 * 1024:
        raise ValueError("Health entry exceeds the 16 KiB size limit.")
    payload = Fernet(_key()).encrypt(serialized)
    with closing(_connect(path)) as conn, conn:
        _verified(conn)
        conn.execute("""INSERT INTO entries (entry_id, encrypted_payload)
            VALUES (?, ?)
            ON CONFLICT(entry_id) DO UPDATE SET encrypted_payload=excluded.encrypted_payload""",
            (_entry_id(day, question), payload))


def get(day: str, question: str, path: Path = DEFAULT_PATH) -> dict | None:
    with closing(_connect(path)) as conn, conn:
        _verified(conn)
        row = conn.execute("SELECT encrypted_payload FROM entries WHERE entry_id=?", (_entry_id(day, question),)).fetchone()
    if not row:
        return None
    record = json.loads(Fernet(_key()).decrypt(row[0]))
    if record.get("day") != day or record.get("question") != question:
        raise RuntimeError("Health entry identity mismatch.")
    return record["answer"]



def delete(day: str, question: str, path: Path = DEFAULT_PATH) -> bool:
    """Offline-only deletion of one encrypted answer; never exposed as a web route."""
    from datetime import date
    if date.fromisoformat(day).isoformat() != day or not question or len(question) > 200:
        raise ValueError("Invalid date or question.")
    with closing(_connect(path)) as conn, conn:
        _verified(conn)
        result = conn.execute("DELETE FROM entries WHERE entry_id=?", (_entry_id(day, question),))
        return result.rowcount == 1


def encrypted_backup(destination: Path, path: Path = DEFAULT_PATH) -> None:
    """Produce a separately encrypted, portable SQLite snapshot; never plaintext backup."""
    destination = Path(destination).expanduser()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Refusing to overwrite backup.")
    with closing(_connect(path)) as source:
        _verified(source)
        snapshot = sqlite3.connect(":memory:")
        try:
            source.backup(snapshot)
            if snapshot.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Vault integrity check failed; backup not created.")
            _verify_encrypted_entries(snapshot)
            raw = snapshot.serialize()
        finally:
            snapshot.close()
    encrypted = Fernet(_key()).encrypt(raw)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(destination.parent, 0o700)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(encrypted)
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        # An interrupted backup must not masquerade as a recoverable snapshot.
        destination.unlink(missing_ok=True)
        raise




def _verify_encrypted_entries(conn) -> int:
    """Authenticate every record and ensure its secret lookup matches its payload."""
    cipher = Fernet(_key())
    count = 0
    for entry_id, encrypted_payload in conn.execute(
        "SELECT entry_id, encrypted_payload FROM entries"
    ):
        try:
            plaintext = cipher.decrypt(encrypted_payload)
            if len(plaintext) > 16 * 1024:
                raise ValueError("Encrypted health entry exceeds size limit.")
            def reject_nonfinite(value):
                raise ValueError("Non-finite JSON number is not allowed.")
            record = json.loads(plaintext, parse_constant=reject_nonfinite)
            day, question, answer = record["day"], record["question"], record["answer"]
            from datetime import date
            if (not isinstance(day, str) or not isinstance(question, str)
                    or not isinstance(answer, dict) or not question
                    or len(question) > 200 or date.fromisoformat(day).isoformat() != day):
                raise RuntimeError("Invalid encrypted health entry.")
            if not isinstance(entry_id, str) or not hmac.compare_digest(entry_id, _entry_id(day, question)):
                raise RuntimeError("Encrypted health entry identity mismatch.")
        except (InvalidToken, ValueError, TypeError, KeyError) as exc:
            raise RuntimeError("Encrypted health entry verification failed.") from exc
        count += 1
    return count


def verify_backup(source: Path) -> int:
    """Offline-only: authenticate a backup, check SQLite integrity, count entries.

    Returns the number of authenticated, validated records without exposing
    answers or writing a restored database.
    """
    source = Path(source).expanduser()
    if source.is_symlink() or not source.is_file():
        raise RuntimeError("Backup source must be a regular file, not a symlink.")
    raw = Fernet(_key()).decrypt(source.read_bytes())
    check = sqlite3.connect(":memory:")
    try:
        check.deserialize(raw)
        _verified(check)
        if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Backup integrity check failed.")
        return _verify_encrypted_entries(check)
    finally:
        check.close()


def restore_backup(source: Path, destination: Path) -> None:
    """Offline restore to a NEW file only. Verify backup and key before writing."""
    source, destination = Path(source).expanduser(), Path(destination).expanduser()
    if source.is_symlink() or not source.is_file():
        raise RuntimeError("Backup source must be a regular file, not a symlink.")
    raw = Fernet(_key()).decrypt(source.read_bytes())
    check = sqlite3.connect(":memory:")
    try:
        check.deserialize(raw)
        _verified(check)
        if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Backup integrity check failed.")
        _verify_encrypted_entries(check)
    finally:
        check.close()
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(destination.parent, 0o700)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        # Never leave a truncated restore destination looking like a vault.
        destination.unlink(missing_ok=True)
        raise
