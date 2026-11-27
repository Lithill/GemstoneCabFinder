import unittest
from datetime import date
from favourite_feed.health_cycle import compare_cycle, GROUPS

class CycleTests(unittest.TestCase):
    # Run the cycle comparison over a fixed date range using only supplied fictional diary entries.
    def compare(self, records):
        return compare_cycle(date(2026,1,20),30,"Fibromyalgia pain",lambda d:records.get(d,[]))

    # Use the recorded period start date and distinguish bleeding categories from missing bleeding answers.
    def test_explicit_start_and_missing(self):
        def entries(bleeding):
            return [{"name":"Period / bleeding today","answer":bleeding},{"name":"Fibromyalgia pain","answer":"Mild"}]
        records={"2026-01-09":entries("None"),"2026-01-10":entries("Period"),
                 "2026-01-12":entries("None"),"2026-01-13":entries("Spotting"),
                 "2026-01-14":[{"name":"Fibromyalgia pain","answer":"Severe"}],
                 "2026-01-15":[{"name":"Period start or end date","answer":"2026-01-10","extras":["detail: Start"]}]}
        result=self.compare(records)
        self.assertEqual(result["starts"],["2026-01-10"])
        self.assertEqual([r["n"] for r in result["rows"]],[1,1,1,0,1])

    # A recorded period day after an unknown day does not establish a new period start.
    def test_no_inferred_start_after_unknown(self):
        result=self.compare({"2026-01-10":[{"name":"Period / bleeding today","answer":"Period"}]})
        self.assertEqual(result["starts"],[])
        self.assertEqual(result["rows"][1]["days"],1)

    # Exclude ambiguous days that fall into overlapping before- and after-start windows.
    def test_overlapping_windows_excluded(self):
        records={"2026-01-10":[{"name":"Period start or end date","answer":"2026-01-10","extras":["detail: Start"]}],
                 "2026-01-16":[{"name":"Period start or end date","answer":"2026-01-16","extras":["detail: Start"]}],
                 "2026-01-13":[{"name":"Period / bleeding today","answer":"None"},{"name":"Fibromyalgia pain","answer":"Severe"}]}
        self.assertEqual(sum(r["n"] for r in self.compare(records)["rows"]),0)
