"""Offline vault encryption and restore regression tests.

No live health data, server configuration, or production database is used.
"""
import os
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet, InvalidToken
from favourite_feed import health_vault


class HealthVaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.key = Fernet.generate_key().decode()
        env = patch.dict(os.environ, {"HEALTH_VAULT_KEY": self.key})
        env.start()
        self.addCleanup(env.stop)
        self.db = Path(self.tmp.name) / "vault.db"
        health_vault.provision(self.db)

    def test_upsert_replaces_same_day_question_only(self):
        health_vault.put("2026-11-20", "Anxiety", {"answer": "Mild"}, self.db)
        health_vault.put("2026-11-20", "Anxiety", {"answer": "Severe"}, self.db)
        health_vault.put("2026-11-21", "Anxiety", {"answer": "None"}, self.db)
        self.assertEqual(health_vault.get("2026-11-20", "Anxiety", self.db), {"answer": "Severe"})
        self.assertEqual(health_vault.get("2026-11-21", "Anxiety", self.db), {"answer": "None"})
        with health_vault._connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0], 2)
            self.assertNotIn(b"Severe", conn.execute("SELECT encrypted_payload FROM entries LIMIT 1").fetchone()[0])
            self.assertEqual([column[1] for column in conn.execute("PRAGMA table_info(entries)")], ["entry_id", "encrypted_payload"])
        raw = self.db.read_bytes()
        self.assertNotIn(b"Anxiety", raw)
        self.assertNotIn(b"2026-11-20", raw)
        self.assertNotIn(b"Severe", raw)

    def test_delete_only_targeted_day_and_question(self):
        health_vault.put("2026-11-20", "Sleep", {"answer": "Mild"}, self.db)
        health_vault.put("2026-11-20", "Anxiety", {"answer": "Severe"}, self.db)
        health_vault.put("2026-11-21", "Sleep", {"answer": "None"}, self.db)
        self.assertTrue(health_vault.delete("2026-11-20", "Sleep", self.db))
        self.assertFalse(health_vault.delete("2026-11-20", "Sleep", self.db))
        self.assertIsNone(health_vault.get("2026-11-20", "Sleep", self.db))
        self.assertEqual(health_vault.get("2026-11-20", "Anxiety", self.db), {"answer": "Severe"})
        self.assertEqual(health_vault.get("2026-11-21", "Sleep", self.db), {"answer": "None"})

    def test_delete_wrong_key_and_invalid_day_fail_closed(self):
        health_vault.put("2026-11-20", "Sleep", {"answer": "Mild"}, self.db)
        with patch.dict(os.environ, {"HEALTH_VAULT_KEY": Fernet.generate_key().decode()}):
            with self.assertRaisesRegex(RuntimeError, "Wrong health vault key"):
                health_vault.delete("2026-11-20", "Sleep", self.db)
        with self.assertRaises(ValueError):
            health_vault.delete("not-a-day", "Sleep", self.db)
        self.assertEqual(health_vault.get("2026-11-20", "Sleep", self.db), {"answer": "Mild"})

    def test_backup_restore_and_wrong_key(self):
        health_vault.put("2026-11-20", "Sleep", {"answer": "Moderate"}, self.db)
        backup = Path(self.tmp.name) / "backup.enc"
        restored = Path(self.tmp.name) / "restored.db"
        health_vault.encrypted_backup(backup, self.db)
        self.assertNotIn(b"Moderate", backup.read_bytes())
        health_vault.restore_backup(backup, restored)
        self.assertEqual(health_vault.get("2026-11-20", "Sleep", restored), {"answer": "Moderate"})
        with self.assertRaises(FileExistsError):
            health_vault.restore_backup(backup, restored)
        with patch.dict(os.environ, {"HEALTH_VAULT_KEY": Fernet.generate_key().decode()}):
            with self.assertRaises(InvalidToken):
                health_vault.restore_backup(backup, Path(self.tmp.name) / "wrong.db")

    def test_backup_with_tampered_encrypted_entry_is_rejected(self):
        health_vault.put("2026-11-20", "Sleep", {"answer": "Mild"}, self.db)
        # Change an encrypted record while keeping the SQLite file structurally valid.
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE entries SET encrypted_payload=?",
                         (b"not-a-valid-fernet-token",))
        backup = Path(self.tmp.name) / "tampered-entry.enc"
        health_vault.encrypted_backup(backup, self.db)
        restored = Path(self.tmp.name) / "tampered-restored.db"
        with self.assertRaisesRegex(RuntimeError, "entry verification failed"):
            health_vault.verify_backup(backup)
        with self.assertRaisesRegex(RuntimeError, "entry verification failed"):
            health_vault.restore_backup(backup, restored)
        self.assertFalse(restored.exists())

    def test_backup_with_mismatched_secret_entry_id_is_rejected(self):
        health_vault.put("2026-11-20", "Sleep", {"answer": "Mild"}, self.db)
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE entries SET entry_id=?", ("0" * 64,))
        backup = Path(self.tmp.name) / "mismatched-entry.enc"
        health_vault.encrypted_backup(backup, self.db)
        with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
            health_vault.verify_backup(backup)

    def test_recovery_drill_restores_multiple_entries_without_touching_original(self):
        """Exercise the full backup/verify/restore/read workflow offline."""
        original = {
            ("2026-11-20", "Sleep"): {"answer": "Moderate", "notes": "private sample"},
            ("2026-11-20", "Anxiety"): {"answer": "Mild"},
            ("2026-11-21", "Sleep"): {"answer": "None"},
        }
        for (day, question), answer in original.items():
            health_vault.put(day, question, answer, self.db)

        backup = Path(self.tmp.name) / "recovery-drill.enc"
        restored = Path(self.tmp.name) / "recovery-drill.db"
        health_vault.encrypted_backup(backup, self.db)
        self.assertEqual(health_vault.verify_backup(backup), len(original))
        self.assertNotIn(b"private sample", backup.read_bytes())

        health_vault.restore_backup(backup, restored)
        for (day, question), answer in original.items():
            self.assertEqual(health_vault.get(day, question, restored), answer)

        # Mutating the restored copy must not change the original vault.
        self.assertTrue(health_vault.delete("2026-11-20", "Sleep", restored))
        self.assertIsNone(health_vault.get("2026-11-20", "Sleep", restored))
        self.assertEqual(
            health_vault.get("2026-11-20", "Sleep", self.db),
            original[("2026-11-20", "Sleep")],
        )
        self.assertEqual(health_vault.verify_backup(backup), len(original))

    def test_verify_backup_authenticates_and_counts_encrypted_entries(self):
        health_vault.put("2026-11-20", "Sleep", {"answer": "Mild"}, self.db)
        health_vault.put("2026-11-21", "Sleep", {"answer": "Severe"}, self.db)
        backup = Path(self.tmp.name) / "verified-backup.enc"
        health_vault.encrypted_backup(backup, self.db)
        self.assertEqual(health_vault.verify_backup(backup), 2)
        self.assertFalse((Path(self.tmp.name) / "verified-backup.db").exists())
        with patch.dict(os.environ, {"HEALTH_VAULT_KEY": Fernet.generate_key().decode()}):
            with self.assertRaises(InvalidToken):
                health_vault.verify_backup(backup)
        corrupted = bytearray(backup.read_bytes())
        corrupted[-1] ^= 1
        backup.write_bytes(corrupted)
        with self.assertRaises(InvalidToken):
            health_vault.verify_backup(backup)

    def test_verify_backup_rejects_symlink(self):
        backup = Path(self.tmp.name) / "verified-backup.enc"
        health_vault.encrypted_backup(backup, self.db)
        linked = Path(self.tmp.name) / "linked-verified-backup.enc"
        linked.symlink_to(backup)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            health_vault.verify_backup(linked)

    def test_failed_backup_write_removes_incomplete_destination(self):
        health_vault.put("2026-11-20", "Sleep", {"answer": "Mild"}, self.db)
        backup = Path(self.tmp.name) / "failed-backup.enc"
        real_fdopen = os.fdopen

        class BrokenWriter:
            def __init__(self, stream):
                self.stream = stream

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return self.stream.__exit__(exc_type, exc, tb)

            def write(self, data):
                self.stream.write(data[:16])
                raise OSError("simulated backup disk full")

        with patch.object(health_vault.os, "fdopen",
                          side_effect=lambda fd, mode: BrokenWriter(real_fdopen(fd, mode))):
            with self.assertRaisesRegex(OSError, "simulated backup disk full"):
                health_vault.encrypted_backup(backup, self.db)
        self.assertFalse(backup.exists())
        self.assertEqual(health_vault.get("2026-11-20", "Sleep", self.db), {"answer": "Mild"})

    def test_failed_restore_write_removes_incomplete_destination(self):
        health_vault.put("2026-11-20", "Sleep", {"answer": "Mild"}, self.db)
        backup = Path(self.tmp.name) / "backup.enc"
        health_vault.encrypted_backup(backup, self.db)
        restored = Path(self.tmp.name) / "failed-restore.db"

        real_fdopen = os.fdopen

        class BrokenWriter:
            def __init__(self, stream):
                self.stream = stream

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return self.stream.__exit__(exc_type, exc, tb)

            def write(self, data):
                self.stream.write(data[:16])
                raise OSError("simulated disk full")

        def broken_fdopen(fd, mode):
            return BrokenWriter(real_fdopen(fd, mode))

        with patch.object(health_vault.os, "fdopen", side_effect=broken_fdopen):
            with self.assertRaisesRegex(OSError, "simulated disk full"):
                health_vault.restore_backup(backup, restored)
        self.assertFalse(restored.exists())
        self.assertEqual(health_vault.get("2026-11-20", "Sleep", self.db), {"answer": "Mild"})

    def test_corrupted_backup_cannot_create_restored_database(self):
        health_vault.put("2026-11-20", "Sleep", {"answer": "Mild"}, self.db)
        backup = Path(self.tmp.name) / "backup.enc"
        health_vault.encrypted_backup(backup, self.db)
        corrupted = bytearray(backup.read_bytes())
        corrupted[len(corrupted) // 2] ^= 1
        backup.write_bytes(corrupted)
        restored = Path(self.tmp.name) / "corrupt-restored.db"
        with self.assertRaises(InvalidToken):
            health_vault.restore_backup(backup, restored)
        self.assertFalse(restored.exists())
        self.assertEqual(health_vault.get("2026-11-20", "Sleep", self.db), {"answer": "Mild"})

    @unittest.skipIf(os.name == "nt", "POSIX permission checks only")
    def test_vault_and_restored_backup_permissions(self):
        self.assertEqual(self.db.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.db.parent.stat().st_mode & 0o777, 0o700)
        backup_dir = Path(self.tmp.name) / "backups"
        backup_dir.mkdir(mode=0o755)
        backup = backup_dir / "health.enc"
        health_vault.encrypted_backup(backup, self.db)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual(backup_dir.stat().st_mode & 0o777, 0o700)
        restore_dir = Path(self.tmp.name) / "restored"
        restore_dir.mkdir(mode=0o755)
        restored = restore_dir / "vault.db"
        health_vault.restore_backup(backup, restored)
        self.assertEqual(restored.stat().st_mode & 0o777, 0o600)
        self.assertEqual(restore_dir.stat().st_mode & 0o777, 0o700)

    @unittest.skipIf(os.name == "nt", "Symlink test requires POSIX support")
    def test_symlink_paths_are_rejected(self):
        linked_vault = Path(self.tmp.name) / "linked-vault.db"
        linked_vault.symlink_to(self.db)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            health_vault.get("2026-11-20", "Sleep", linked_vault)
        with self.assertRaises(FileExistsError):
            health_vault.provision(linked_vault)
        backup = Path(self.tmp.name) / "backup.enc"
        health_vault.encrypted_backup(backup, self.db)
        linked_backup = Path(self.tmp.name) / "linked-backup.enc"
        linked_backup.symlink_to(backup)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            health_vault.restore_backup(linked_backup, Path(self.tmp.name) / "new.db")
        with self.assertRaises(FileExistsError):
            health_vault.encrypted_backup(linked_backup, self.db)

    def test_backup_refuses_overwrite(self):
        backup = Path(self.tmp.name) / "backup.enc"
        health_vault.encrypted_backup(backup, self.db)
        original = backup.read_bytes()
        with self.assertRaises(FileExistsError):
            health_vault.encrypted_backup(backup, self.db)
        self.assertEqual(backup.read_bytes(), original)

    def test_legacy_plaintext_metadata_schema_is_rejected(self):
        legacy = Path(self.tmp.name) / "legacy.db"
        with sqlite3.connect(legacy) as conn:
            conn.execute("CREATE TABLE entries (day TEXT NOT NULL, question TEXT NOT NULL, encrypted_payload BLOB NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(day, question))")
            conn.execute("CREATE TABLE vault_meta (key TEXT PRIMARY KEY, value BLOB NOT NULL)")
            conn.execute("INSERT INTO vault_meta VALUES ('key_check', ?)", (Fernet(self.key.encode()).encrypt(b'health-vault-v1'),))
        with self.assertRaisesRegex(RuntimeError, "Unsupported health vault schema"):
            health_vault.get("2026-11-20", "Anxiety", legacy)
        with self.assertRaisesRegex(RuntimeError, "Unsupported health vault schema"):
            health_vault.encrypted_backup(Path(self.tmp.name) / "legacy.enc", legacy)
        self.assertFalse((Path(self.tmp.name) / "legacy.enc").exists())

    def test_failed_provision_removes_incomplete_database(self):
        failed = Path(self.tmp.name) / "failed-vault.db"
        with patch.object(health_vault.sqlite3, "connect", side_effect=sqlite3.OperationalError("simulated disk error")):
            with self.assertRaises(sqlite3.OperationalError):
                health_vault.provision(failed)
        self.assertFalse(failed.exists())
        self.assertEqual(health_vault.get("2026-11-20", "Anxiety", self.db), None)

    def test_missing_key_fails_closed(self):
        with patch.dict(os.environ, {"HEALTH_VAULT_KEY": ""}):
            with self.assertRaises(RuntimeError):
                health_vault.get("2026-11-20", "Anxiety", self.db)

    def test_password_hash_verification(self):
        encoded = health_vault.password_hash("a long unique passphrase")
        self.assertTrue(health_vault.verify_password("a long unique passphrase", encoded))
        self.assertFalse(health_vault.verify_password("wrong password", encoded))
        self.assertFalse(health_vault.verify_password("anything", "scrypt$32768$8$1$%%%$%%%"))
        with self.assertRaises(ValueError):
            health_vault.password_hash("short")


if __name__ == "__main__":
    unittest.main()
