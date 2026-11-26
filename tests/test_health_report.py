import unittest
from datetime import date
from favourite_feed.health_report import build_report

class ReportTests(unittest.TestCase):
    def test_empty(self):
        r=build_report(date(2026,1,30),30,[],lambda d:[],lambda d:None)
        self.assertEqual(r["start"],"2026-01-01")
        self.assertEqual(r["counts"]["diary"],0)
        self.assertEqual(r["symptoms"],[])
        self.assertEqual(r["associations"],[])

    def test_history_and_explicit_zero(self):
        items=[{"name":"Example","category":"Medication","history":[
            {"day":"2025-12-01","status":"Taking","dose":"Example dose"},
            {"day":"2026-01-15","status":"Stopped","dose":""},
            {"day":"2026-02-01","status":"Taking","dose":"Future"}]}]
        def read(d):
            return [{"name":"Fibromyalgia pain","answer":"None"}] if d=="2026-01-02" else []
        r=build_report(date(2026,1,30),30,items,read,lambda d:None)
        self.assertEqual(r["symptoms"][0]["mean"],0)
        self.assertEqual(r["symptoms"][0]["n"],1)
        self.assertEqual(r["current"][0]["status"],"Stopped")
        self.assertEqual(len(r["changes"]),1)
        self.assertEqual(r["monthly"][0]["rows"][0]["n"],1)
