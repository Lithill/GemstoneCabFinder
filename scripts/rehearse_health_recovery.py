"""Isolated encrypted health-vault disaster recovery rehearsal.

Run: python scripts/rehearse_health_recovery.py
Creates only synthetic answers inside a disposable temporary directory.
Never reads the production vault or gemstone database, and never deploys.
"""
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from unittest.mock import patch

from cryptography.fernet import Fernet

# Allow direct execution from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from favourite_feed import health_diary_bridge, health_vault


# Fixed fictional test data, not records from the personal diary.
DAY = "2026-11-21"
FICTIONAL_DIARY = [
    {"name": "Hot flushes", "answer": "Yes", "extras": [], "notes": "do not retain"},
    {"name": "Brain fog", "answer": "Mild", "extras": [], "notes": ""},
    {"name": "Weight measurement", "answer": "68.5", "extras": ["unit: kg"], "notes": ""},
]


def rehearse() -> dict:
    """Return non-sensitive checks; fail loudly on any recovery discrepancy."""
    # Isolate every test file in a temporary directory that is cleaned up when the context exits.
    with tempfile.TemporaryDirectory(prefix="synthetic-health-recovery-") as temp:
        root = Path(temp)
        original = root / "fictional-original.db"
        encrypted = root / "fictional-backup.enc"
        restored = root / "fictional-restored.db"
        # Generate a disposable key and temporarily override the environment for this rehearsal only.
        key = Fernet.generate_key().decode("ascii")
        with patch.dict(os.environ, {"HEALTH_VAULT_KEY": key}):
            health_vault.provision(original)
            count = health_diary_bridge.save_diary_offline(DAY, FICTIONAL_DIARY, path=original)
            if count != len(FICTIONAL_DIARY):
                raise AssertionError("Initial synthetic check-in count mismatch.")
            # Read back the saved fictional entries to establish the expected recovery result and confirm notes are omitted.
            expected = health_diary_bridge.read_diary_offline(DAY, path=original)
            if any(item["notes"] for item in expected):
                raise AssertionError("Notes unexpectedly persisted.")
            # Create an encrypted snapshot and verify that all synthetic entries authenticate.
            health_vault.encrypted_backup(encrypted, path=original)
            verified_count = health_vault.verify_backup(encrypted)
            if verified_count != count:
                raise AssertionError("Encrypted backup did not verify every entry.")
            # Check that these particular sample strings do not appear directly in the backup bytes; authentication checks provide the stronger integrity test.
            if b"Brain fog" in encrypted.read_bytes() or b"do not retain" in encrypted.read_bytes():
                raise AssertionError("Backup contains unencrypted synthetic answers.")
            # Simulate total loss of the working vault, without touching anything else.
            original.unlink()
            if original.exists():
                raise AssertionError("Failed to simulate vault loss.")
            # Restore the verified backup to a different path and compare the recovered answers with the expected values.
            health_vault.restore_backup(encrypted, restored)
            recovered = health_diary_bridge.read_diary_offline(DAY, path=restored)
            if recovered != expected:
                raise AssertionError("Restored check-in differs from original.")
            # Prove the restored vault is usable for subsequent legitimate edits.
            health_diary_bridge.save_diary_offline(
                DAY, [{"name": "Brain fog", "answer": "Moderate", "extras": [], "notes": ""}],
                path=restored,
            )
            updated = health_diary_bridge.read_diary_offline(DAY, path=restored)
            if len(updated) != count or not any(
                item["name"] == "Brain fog" and item["answer"] == "Moderate" for item in updated
            ):
                raise AssertionError("Restored vault cannot safely accept edits.")
            # A backup cannot be restored with a different encryption key.
            with patch.dict(os.environ, {"HEALTH_VAULT_KEY": Fernet.generate_key().decode("ascii")}):
                wrong_target = root / "wrong-key.db"
                try:
                    health_vault.restore_backup(encrypted, wrong_target)
                except Exception:
                    pass
                else:
                    raise AssertionError("Wrong-key restore unexpectedly succeeded.")
                if wrong_target.exists():
                    raise AssertionError("Wrong-key restore left a database behind.")
            # Refuse overwrite of an existing restored vault.
            try:
                health_vault.restore_backup(encrypted, restored)
            except FileExistsError:
                pass
            else:
                raise AssertionError("Restore overwrote an existing vault.")
            # Return only non-sensitive counts and test outcomes, not the encryption key or diary contents.
            return {
                "synthetic_entries": count,
                "authenticated_backup_entries": verified_count,
                "restored_entries": len(recovered),
                "post_restore_edit": "passed",
                "wrong_key_rejected": True,
                "overwrite_rejected": True,
                "temporary_files_removed": True,
            }


if __name__ == "__main__":
    print("Synthetic encrypted health recovery rehearsal:", rehearse())
