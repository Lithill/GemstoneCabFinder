"""Offline vault encryption and restore regression tests.

No live health data, server configuration, or production database is used.
"""
import os
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
