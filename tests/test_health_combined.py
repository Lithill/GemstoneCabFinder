import unittest
from datetime import date
from favourite_feed.health_combined import compare_combined

class CombinedTests(unittest.TestCase):
    def test_context_and_change_between_exposure_and_outcome(self):
        logs={"2026-01-09":{"rest":False,"sessions":[{}]},
              "2026-01-08":{"rest":True,"sessions":[]}}
        items=[{"category":"Medication","history":[{"day":"2026-01-10"}]}]
        def read(d):
            return [{"name":"Period / bleeding today","answer":"Period" if d=="2026-01-10" else "None"},
                    {"name":"Fibromyalgia pain","answer":"Mild"}]
        result=compare_combined(date(2026,1,10),30,1,"Fibromyalgia pain",items,read,logs.get)
        rows={(r["context"],r["recent"]):r for r in result["rows"]}
        self.assertEqual(rows["Period",True]["active_n"],1)
        self.assertEqual(rows["No bleeding",False]["rest_n"],1)
        self.assertEqual(result["excluded"]["activity"],28)

    def test_unknown_bleeding_excluded(self):
        result=compare_combined(date(2026,1,10),30,0,"Fibromyalgia pain",[],
            lambda d:[{"name":"Fibromyalgia pain","answer":"None"}],
            lambda d:{"rest":True,"sessions":[]})
        self.assertEqual(result["excluded"]["bleeding"],30)
        self.assertTrue(all(r["rest"] is None for r in result["rows"]))

    def test_zero_is_valid_and_threshold(self):
        def log(d):
            return {"rest":True,"sessions":[]} if d<"2026-01-06" else {"rest":False,"sessions":[{}]}
        def read(d):
            return [{"name":"Period / bleeding today","answer":"None"},
                    {"name":"Fibromyalgia pain","answer":"Severe" if d<"2026-01-06" else "None"}]
        result=compare_combined(date(2026,1,10),10,0,"Fibromyalgia pain",[],read,log)
        row=result["rows"][0]
        self.assertEqual((row["rest"],row["active"],row["direction"]),(3,0,"lower"))
