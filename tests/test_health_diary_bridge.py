"""Offline integration: prototype diary -> validation -> encrypted vault -> diary."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from favourite_feed import health_diary_bridge as bridge, health_entries, health_vault


def item(name, answer, extras=None, notes=""):
    return {"name": name, "answer": answer, "extras": extras or [], "notes": notes}


class DiaryBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "fictional-vault.db"
        self.environment = patch.dict(os.environ, {"HEALTH_VAULT_KEY": Fernet.generate_key().decode()})
        self.environment.start()
        health_vault.provision(self.db)

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def test_guided_and_quick_entries_round_trip_without_notes(self):
        day = "2026-11-21"
        diary = [
            item("Hot flushes", "Yes", notes="Private note that must never be saved"),
            item("Brain fog", "Moderate"),
            item("Weight measurement", "67.5", ["unit: kg"]),
            item("Difficulty sleeping / insomnia", "Mild", ["hours: 6.5"]),
            item("Period start or end date", "2026-11-20", ["detail: Start"]),
            item("Period / bleeding today", "Period", ["flow: Light"]),
        ]
        self.assertEqual(bridge.save_diary_offline(day, diary, path=self.db), 6)
        self.assertEqual(health_entries.get_validated(day, "Weight measurement", path=self.db),
                         {"answer": 67.5, "unit": "kg"})
        self.assertEqual(health_entries.get_validated(day, "Difficulty sleeping / insomnia", path=self.db),
                         {"answer": "Mild", "hours": 6.5})
        restored = bridge.read_diary_offline(day, path=self.db)
        self.assertEqual(len(restored), 6)
        self.assertTrue(all(entry["notes"] == "" for entry in restored))
        self.assertIn(item("Weight measurement", "67.5", ["unit: kg"]), restored)
        self.assertNotIn(b"Private note", self.db.read_bytes())

    def test_bad_second_answer_does_not_write_first(self):
        day = "2026-11-21"
        with self.assertRaises(ValueError):
            bridge.save_diary_offline(day, [
                item("Hot flushes", "Yes"),
                item("Brain fog", "Unrecognized"),
            ], path=self.db)
        self.assertIsNone(health_entries.get_validated(day, "Hot flushes", path=self.db))

    def test_duplicate_question_rejected_without_overwrite(self):
        day = "2026-11-21"
        bridge.save_diary_offline(day, [item("Brain fog", "Mild")], path=self.db)
        with self.assertRaises(ValueError):
            bridge.save_diary_offline(day, [
                item("Brain fog", "Severe"),
                item("Brain fog", "Moderate"),
            ], path=self.db)
        self.assertEqual(health_entries.get_validated(day, "Brain fog", path=self.db), {"answer": "Mild"})

    def test_malformed_extras_and_nonfinite_numbers_rejected(self):
        for bad in [
            item("Weight measurement", "nan", ["unit: kg"]),
            item("Weight measurement", "12", ["unit: kg", "unit: lb"]),
            item("Difficulty sleeping / insomnia", "Mild", ["hours: inf"]),
            item("Hot flushes", "Yes", ["detail: ignored"]),
            item("Brain fog", "Mild", ["badextra"]),
        ]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    bridge.save_diary_offline("2026-11-21", [bad], path=self.db)

    def test_empty_diary_requires_valid_date_and_vault(self):
        with self.assertRaises(ValueError):
            bridge.save_diary_offline("2026-02-30", [], path=self.db)
        with self.assertRaises(FileNotFoundError):
            bridge.save_diary_offline("2026-11-21", [], path=Path(self.temp.name) / "missing.db")
        self.assertEqual(bridge.save_diary_offline("2026-11-21", [], path=self.db), 0)


if __name__ == "__main__":
    unittest.main()
