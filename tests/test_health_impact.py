import unittest
from datetime import date
from favourite_feed.health_impact import compare


class ImpactTests(unittest.TestCase):
    # Exclude the change date and distinguish an explicit zero score from missing follow-up answers.
    def test_missing_and_change_day(self):
        def read(day):
            if day == "2026-01-10":
                raise AssertionError("Change day must not be read")
            return [{"name": "Brain fog", "answer": "None"}] if day == "2026-01-09" else []
        row = compare(date(2026,1,10), 7, date(2026,1,12), read)[0]
        self.assertEqual(row["before"], 0)
        self.assertIsNone(row["after"])
        self.assertEqual(row["direction"], "insufficient")

    # Seven recorded days on each side of a change should identify the lower average severity.
    def test_lower(self):
        def read(day):
            return [{"name": "Brain fog", "answer": "Severe" if day < "2026-01-10" else "Mild"}]
        row = compare(date(2026,1,10), 7, date(2026,1,17), read)[0]
        self.assertEqual((row["before_n"], row["after_n"]), (7,7))
        self.assertEqual(row["direction"], "lower")

    # Never read future dates; incomplete follow-up may leave insufficient observations.
    def test_future_excluded(self):
        def read(day):
            self.assertLessEqual(day, "2026-01-12")
            return [{"name": "Brain fog", "answer": "Mild"}]
        row = compare(date(2026,1,10), 7, date(2026,1,12), read)[0]
        self.assertEqual(row["after_n"], 2)
        self.assertEqual(row["direction"], "insufficient")
