import unittest
from datetime import date
from favourite_feed.health_review import review

class ReviewTests(unittest.TestCase):
    # Compare two equal seven-day periods ending yesterday, not including the current partial day.
    def test_equal_complete_windows(self):
        result=review(date(2026,1,15),7,[],lambda d:[],lambda d:None)
        self.assertEqual((result["previous"]["start"],result["previous"]["end"]),("2026-01-01","2026-01-07"))
        self.assertEqual((result["current"]["start"],result["current"]["end"]),("2026-01-08","2026-01-14"))
        self.assertEqual(result["rows"],[])

    # Calculate averages from recorded answers only and count explicit no symptoms as zero.
    def test_change_and_missing(self):
        def read(d):
            if d in ("2026-01-01","2026-01-02","2026-01-03"):
                return [{"name":"Fibromyalgia pain","answer":"Severe"}]
            if d in ("2026-01-08","2026-01-09","2026-01-10"):
                return [{"name":"Fibromyalgia pain","answer":"None"}]
            return []
        result=review(date(2026,1,15),7,[],read,lambda d:None)
        row=result["rows"][0]
        self.assertEqual((row["before"],row["after"],row["before_n"],row["after_n"]),(3,0,3,3))
        self.assertEqual(row["direction"],"lower")
        self.assertEqual(result["current"]["counts"]["diary_days"],3)

    # Count exercise, rest and minutes separately and place lifestyle changes in the correct review window.
    def test_activity_and_changes(self):
        logs={"2026-01-08":{"rest":True,"sessions":[]},"2026-01-09":{"rest":False,"sessions":[{"minutes":20}]}}
        items=[{"name":"Example habit","history":[{"day":"2026-01-10","status":"Ongoing","dose":""}]}]
        result=review(date(2026,1,15),7,items,lambda d:[],logs.get)
        current=result["current"]
        self.assertEqual((current["counts"]["active"],current["counts"]["rest"],current["counts"]["minutes"]),(1,1,20))
        self.assertEqual(len(current["changes"]),1)
        self.assertEqual(result["previous"]["changes"],[])
