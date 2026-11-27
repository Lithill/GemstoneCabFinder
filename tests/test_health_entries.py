"""Synthetic-only offline integration tests for validated encrypted entries."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from favourite_feed import health_entries, health_vault


class ValidatedHealthEntryTests(unittest.TestCase):
    # Provision an isolated encrypted database with a freshly generated test key.
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "synthetic-health.db"
        self.key = Fernet.generate_key().decode()
        self.environment = patch.dict(os.environ, {"HEALTH_VAULT_KEY": self.key})
        self.environment.start()
        health_vault.provision(self.db)

    # Restore environment settings and remove the temporary database.
    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    # Check missing answers, saving, editing and absence of sample plaintext in the file.
    def test_validated_write_read_and_same_day_edit(self):
        day = "2026-11-21"
        question = "Brain fog"
        self.assertIsNone(health_entries.get_validated(day, question, path=self.db))
        health_entries.put_validated(day, question, {"answer": "Mild"}, path=self.db)
        self.assertEqual(health_entries.get_validated(day, question, path=self.db), {"answer": "Mild"})
        health_entries.put_validated(day, question, {"answer": "Severe"}, path=self.db)
        self.assertEqual(health_entries.get_validated(day, question, path=self.db), {"answer": "Severe"})
        self.assertNotIn(b"Brain fog", self.db.read_bytes())
        self.assertNotIn(b"Severe", self.db.read_bytes())

    # Reject invalid edits while retaining the previously saved answer.
    def test_invalid_edit_does_not_overwrite_valid_answer(self):
        day, question = "2026-11-21", "Hot flushes"
        health_entries.put_validated(day, question, {"answer": "Yes"}, path=self.db)
        for bad in ({"answer": "Maybe"}, {"answer": "No", "notes": "not permitted"}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    health_entries.put_validated(day, question, bad, path=self.db)
                self.assertEqual(health_entries.get_validated(day, question, path=self.db), {"answer": "Yes"})

    # Reject unknown questions and impossible dates on reads or writes.
    def test_unknown_question_and_invalid_date_rejected(self):
        with self.assertRaises(ValueError):
            health_entries.put_validated("2026-11-21", "Unknown", {"answer": "Mild"}, path=self.db)
        with self.assertRaises(ValueError):
            health_entries.get_validated("2026-02-30", "Brain fog", path=self.db)
        with self.assertRaises(ValueError):
            health_entries.get_validated("2026-11-21", "Unknown", path=self.db)

    # Delete only the selected record and preserve other questions and days.
    def test_delete_only_one_day_and_question(self):
        entries = [
            ("2026-11-20", "Brain fog", {"answer": "Mild"}),
            ("2026-11-20", "Hot flushes", {"answer": "Yes"}),
            ("2026-11-21", "Brain fog", {"answer": "Severe"}),
        ]
        for day, question, answer in entries:
            health_entries.put_validated(day, question, answer, path=self.db)
        self.assertTrue(health_entries.delete_validated("2026-11-20", "Brain fog", path=self.db))
        self.assertFalse(health_entries.delete_validated("2026-11-20", "Brain fog", path=self.db))
        self.assertIsNone(health_entries.get_validated("2026-11-20", "Brain fog", path=self.db))
        self.assertEqual(health_entries.get_validated("2026-11-20", "Hot flushes", path=self.db), {"answer": "Yes"})
        self.assertEqual(health_entries.get_validated("2026-11-21", "Brain fog", path=self.db), {"answer": "Severe"})

    # Validate deletion targets before changing stored data.
    def test_delete_rejects_unknown_question_and_invalid_date(self):
        health_entries.put_validated("2026-11-21", "Brain fog", {"answer": "Mild"}, path=self.db)
        for day, question in [
            ("2026-02-30", "Brain fog"),
            ("2026-11-21", "Not a symptom"),
            (None, "Brain fog"),
        ]:
            with self.subTest(day=day, question=question):
                with self.assertRaises(ValueError):
                    health_entries.delete_validated(day, question, path=self.db)
        self.assertEqual(health_entries.get_validated("2026-11-21", "Brain fog", path=self.db), {"answer": "Mild"})

    # An unrelated encryption key must not permit deletion.
    def test_delete_wrong_key_does_not_remove_answer(self):
        health_entries.put_validated("2026-11-21", "Brain fog", {"answer": "Mild"}, path=self.db)
        with patch.dict(os.environ, {"HEALTH_VAULT_KEY": Fernet.generate_key().decode()}):
            with self.assertRaises(RuntimeError):
                health_entries.delete_validated("2026-11-21", "Brain fog", path=self.db)
        self.assertEqual(health_entries.get_validated("2026-11-21", "Brain fog", path=self.db), {"answer": "Mild"})

    # Writing must not silently provision a missing vault.
    def test_missing_vault_is_never_automatically_created(self):
        missing = Path(self.temp.name) / "never-create.db"
        with self.assertRaises(FileNotFoundError):
            health_entries.put_validated("2026-11-21", "Brain fog", {"answer": "Mild"}, path=missing)
        self.assertFalse(missing.exists())

    # Reject both reading and writing with an incorrect key.
    def test_wrong_key_does_not_read_or_overwrite(self):
        health_entries.put_validated("2026-11-21", "Brain fog", {"answer": "Mild"}, path=self.db)
        with patch.dict(os.environ, {"HEALTH_VAULT_KEY": Fernet.generate_key().decode()}):
            with self.assertRaises(RuntimeError):
                health_entries.get_validated("2026-11-21", "Brain fog", path=self.db)
            with self.assertRaises(RuntimeError):
                health_entries.put_validated("2026-11-21", "Brain fog", {"answer": "Severe"}, path=self.db)
        self.assertEqual(health_entries.get_validated("2026-11-21", "Brain fog", path=self.db), {"answer": "Mild"})


if __name__ == "__main__":
    unittest.main()
