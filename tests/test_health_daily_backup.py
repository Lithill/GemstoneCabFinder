from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
from favourite_feed.health_vault import provision, put, get, restore_backup
from scripts.health_daily_backup import rotate

class DailyBackupTests(unittest.TestCase):
    # Simulate nine daily backups, verify seven remain, restore the latest answer and check private permissions.
    def test_rotation_and_recovery(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"HEALTH_VAULT_KEY": Fernet.generate_key().decode()}):
            root = Path(tmp)
            vault = root / "fictional.db"
            folder = root / "backups"
            provision(vault)
            start = datetime(2026, 11, 1, tzinfo=timezone.utc)
            for i in range(9):
                put("2026-11-01", "Brain fog", {"severity": i}, vault)
                latest = rotate(vault, folder, start + timedelta(days=i))
            self.assertEqual(len(list(folder.glob("health-*.enc"))), 7)
            self.assertFalse((folder / "health-2026-11-01.enc").exists())
            self.assertEqual(rotate(vault, folder, start + timedelta(days=8)), latest)
            restored = root / "restored.db"
            restore_backup(latest, restored)
            self.assertEqual(get("2026-11-01", "Brain fog", restored), {"severity": 8})
            self.assertEqual(latest.stat().st_mode & 0o777, 0o600)
            self.assertEqual(folder.stat().st_mode & 0o777, 0o700)

    # Refresh the same day's backup and simulate a failed replacement to ensure the last successful backup survives.
    def test_refresh_and_failed_replacement(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"HEALTH_VAULT_KEY": Fernet.generate_key().decode()}):
            root = Path(tmp)
            vault = root / "fictional.db"
            folder = root / "backups"
            provision(vault)
            now = datetime(2026, 11, 26, tzinfo=timezone.utc)
            put("2026-11-26", "Brain fog", {"severity": 1}, vault)
            target = rotate(vault, folder, now, refresh=True)
            put("2026-11-26", "Brain fog", {"severity": 2}, vault)
            self.assertEqual(rotate(vault, folder, now, refresh=True), target)
            self.assertEqual(len(list(folder.glob("health-*.enc"))), 1)
            previous = target.read_bytes()
            with patch("scripts.health_daily_backup.encrypted_backup", side_effect=OSError("test failure")):
                with self.assertRaises(OSError):
                    rotate(vault, folder, now, refresh=True)
            self.assertEqual(target.read_bytes(), previous)
            restored = root / "restored.db"
            restore_backup(target, restored)
            self.assertEqual(get("2026-11-26", "Brain fog", restored), {"severity": 2})
