import unittest
from datetime import date
from favourite_feed.health_exercise import validate, compare_exercise


class ExerciseTests(unittest.TestCase):
    # Accept a valid exercise session but reject simultaneous rest and exercise or Boolean durations.
    def test_validation(self):
        session = {"activity":"Walking","minutes":30,"intensity":"Light"}
        self.assertEqual(validate({"rest":False,"sessions":[session]})["sessions"], [session])
        for bad in ({"rest":True,"sessions":[session]}, {"rest":False,"sessions":[dict(session, minutes=True)]}):
            with self.assertRaises(ValueError):
                validate(bad)

    # Compare next-day symptom scores after explicit rest and exercise; one observation per group is insufficient.
    def test_lag_and_missing(self):
        logs = {"2026-01-08":{"rest":True,"sessions":[]},
                "2026-01-09":{"rest":False,"sessions":[{"activity":"Walking","minutes":30,"intensity":"Light"}]}}
        def symptoms(day):
            return [{"name":"Brain fog","answer":"None" if day=="2026-01-10" else "Severe"}]
        result = compare_exercise(date(2026,1,10),30,1,logs.get,symptoms)
        self.assertEqual(result["counts"], {"rest":1,"active":1})
        row = result["rows"][0]
        self.assertEqual((row["rest"],row["active"]), (3,0))
        self.assertEqual(row["direction"], "insufficient")

    # Unknown activity days must be excluded without reading their symptoms.
    def test_no_records(self):
        result = compare_exercise(date(2026,1,10),30,0,lambda d:None,lambda d:self.fail("Unknown days excluded"))
        self.assertEqual(result["rows"], [])
