"""Synthetic-only tests for atomic offline symptom check-ins."""
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from favourite_feed import health_checkins, health_entries, health_vault


class OfflineCheckinTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "synthetic-vault.db"
        self.environment = patch.dict(os.environ, {"HEALTH_VAULT_KEY": Fernet.generate_key().decode()})
        self.environment.start()
        health_vault.provision(self.db)

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def test_multi_question_checkin_and_same_day_edit(self):
        day = "2026-11-21"
        answers = {
            "Hot flushes": {"answer": "Yes"},
            "Brain fog": {"answer": "Mild"},
            "Difficulty sleeping / insomnia": {"answer": "Moderate", "hours": 5.5},
        }
        self.assertEqual(health_checkins.put_checkin(day, answers, path=self.db), 3)
        self.assertEqual(health_entries.get_validated(day, "Brain fog", path=self.db), {"answer": "Mild"})
        self.assertEqual(health_checkins.put_checkin(day, {"Brain fog": {"answer": "Severe"}}, path=self.db), 1)
        self.assertEqual(health_entries.get_validated(day, "Brain fog", path=self.db), {"answer": "Severe"})
        self.assertEqual(health_entries.get_validated(day, "Hot flushes", path=self.db), {"answer": "Yes"})
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0], 3)
        raw = self.db.read_bytes()
        self.assertNotIn(b"Brain fog", raw)
        self.assertNotIn(b"Severe", raw)

    def test_invalid_question_rejects_whole_checkin(self):
        day = "2026-11-21"
        with self.assertRaises(ValueError):
            health_checkins.put_checkin(day, {
                "Hot flushes": {"answer": "Yes"},
                "Brain fog": {"answer": "Not a severity"},
            }, path=self.db)
        self.assertIsNone(health_entries.get_validated(day, "Hot flushes", path=self.db))
        self.assertIsNone(health_entries.get_validated(day, "Brain fog", path=self.db))

    def test_invalid_edit_keeps_existing_answers(self):
        day = "2026-11-21"
        health_checkins.put_checkin(day, {"Hot flushes": {"answer": "Yes"}}, path=self.db)
        with self.assertRaises(ValueError):
            health_checkins.put_checkin(day, {
                "Hot flushes": {"answer": "No"},
                "Weight measurement": {"answer": float("nan"), "unit": "kg"},
            }, path=self.db)
        self.assertEqual(health_entries.get_validated(day, "Hot flushes", path=self.db), {"answer": "Yes"})

    def test_database_failure_rolls_back_entire_checkin(self):
        """A database error on a later row must undo earlier inserts."""
        day = "2026-11-21"
        health_checkins.put_checkin(day, {"Brain fog": {"answer": "Mild"}}, path=self.db)
        target_id = health_vault._entry_id(day, "Hot flushes")
        with sqlite3.connect(self.db) as conn:
            conn.execute(f"""
                CREATE TRIGGER reject_hot_flushes BEFORE INSERT ON entries
                WHEN NEW.entry_id = '{target_id}'
                BEGIN
                    SELECT RAISE(ABORT, 'simulated failure');
                END
            """)
        with self.assertRaises(sqlite3.IntegrityError):
            health_checkins.put_checkin(day, {
                "Brain fog": {"answer": "Severe"},
                "Hot flushes": {"answer": "Yes"},
            }, path=self.db)
        self.assertEqual(health_entries.get_validated(day, "Brain fog", path=self.db), {"answer": "Mild"})
        self.assertIsNone(health_entries.get_validated(day, "Hot flushes", path=self.db))

    def test_missing_vault_is_not_created(self):
        missing = Path(self.temp.name) / "not-provisioned.db"
        with self.assertRaises(FileNotFoundError):
            health_checkins.put_checkin("2026-11-21", {"Brain fog": {"answer": "Mild"}}, path=missing)
        self.assertFalse(missing.exists())

    def test_wrong_key_does_not_change_existing_entries(self):
        day = "2026-11-21"
        health_checkins.put_checkin(day, {"Brain fog": {"answer": "Mild"}}, path=self.db)
        with patch.dict(os.environ, {"HEALTH_VAULT_KEY": Fernet.generate_key().decode()}):
            with self.assertRaises(RuntimeError):
                health_checkins.put_checkin(day, {"Brain fog": {"answer": "Severe"}}, path=self.db)
        self.assertEqual(health_entries.get_validated(day, "Brain fog", path=self.db), {"answer": "Mild"})

    def test_empty_checkin_is_noop_only_with_valid_vault(self):
        self.assertEqual(health_checkins.put_checkin("2026-11-21", {}, path=self.db), 0)
        missing = Path(self.temp.name) / "no-vault.db"
        with self.assertRaises(FileNotFoundError):
            health_checkins.put_checkin("2026-11-21", {}, path=missing)
        self.assertFalse(missing.exists())
        with patch.dict(os.environ, {"HEALTH_VAULT_KEY": Fernet.generate_key().decode()}):
            with self.assertRaises(RuntimeError):
                health_checkins.put_checkin("2026-11-21", {}, path=self.db)

    def test_empty_checkin_preserves_existing_encrypted_rows(self):
        day = "2026-11-21"
        health_checkins.put_checkin(day, {
            "Brain fog": {"answer": "Mild"},
            "Hot flushes": {"answer": "No"},
        }, path=self.db)
        with sqlite3.connect(self.db) as conn:
            before = conn.execute(
                "SELECT entry_id, encrypted_payload FROM entries ORDER BY entry_id"
            ).fetchall()
        self.assertEqual(health_checkins.put_checkin(day, {}, path=self.db), 0)
        with sqlite3.connect(self.db) as conn:
            after = conn.execute(
                "SELECT entry_id, encrypted_payload FROM entries ORDER BY entry_id"
            ).fetchall()
        self.assertEqual(after, before)

    def test_empty_checkin_rejects_unverified_vault_schema(self):
        invalid = Path(self.temp.name) / "wrong-schema.db"
        with sqlite3.connect(invalid) as conn:
            conn.execute("CREATE TABLE entries (day TEXT, question TEXT, answer TEXT)")
        with self.assertRaises(RuntimeError):
            health_checkins.put_checkin("2026-11-21", {}, path=invalid)
        with sqlite3.connect(invalid) as conn:
            self.assertEqual(
                [row[1] for row in conn.execute("PRAGMA table_info(entries)")],
                ["day", "question", "answer"],
            )

    def test_empty_checkin_rejects_invalid_calendar_dates(self):
        for invalid_day in (None, 20261121, "", "not-a-date", "2026-02-30", "2026-1-2"):
            with self.subTest(day=invalid_day):
                with self.assertRaises(ValueError):
                    health_checkins.put_checkin(invalid_day, {}, path=self.db)
        self.assertEqual(health_checkins.put_checkin("2026-11-21", {}, path=self.db), 0)

    def test_empty_checkin_rejects_bad_input(self):
        for invalid in (None, [], {"not a question": {"answer": "Yes"}}):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    health_checkins.put_checkin("2026-11-21", invalid, path=self.db)


if __name__ == "__main__":
    unittest.main()
