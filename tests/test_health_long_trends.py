import unittest
from datetime import date
from favourite_feed.health_long_trends import monthly_trends

class LongTrendsTests(unittest.TestCase):
    # Check calendar month boundaries, leap-year February and the partial current month.
    def test_month_boundaries_and_partial(self):
        rows=monthly_trends(date(2024,3,5),3,lambda d:None)
        self.assertEqual([r["month"] for r in rows],["2024-01","2024-02","2024-03"])
        self.assertEqual([r["days"] for r in rows],[31,29,5])
        self.assertEqual([r["partial"] for r in rows],[False,False,True])
        self.assertTrue(all(r["mean"] is None for r in rows))

    # Include explicit zero severity in the mean and leave months with no answers without an average.
    def test_missing_and_zero_distinct(self):
        answers={"2026-01-01":{"answer":"None"},"2026-01-02":{"answer":"Severe"}}
        rows=monthly_trends(date(2026,2,1),3,answers.get)
        self.assertEqual(rows[0]["month"],"2025-12")
        self.assertEqual((rows[1]["mean"],rows[1]["n"],rows[1]["none"],rows[1]["severe"]),(1.5,2,1,1))
        self.assertIsNone(rows[2]["mean"])
