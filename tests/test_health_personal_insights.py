import unittest
from datetime import date
from favourite_feed.health_answers import validate_entry
from favourite_feed.health_personal_insights import summarize


class PersonalInsightsTests(unittest.TestCase):
    def test_pain_question(self):
        for value in ("None","Mild","Moderate","Severe"):
            self.assertEqual(validate_entry("2026-01-01","Fibromyalgia pain",{"answer":value})["answer"]["answer"],value)

    def test_empty(self):
        result=summarize(date(2026,1,30),[],lambda d:[],lambda d:None)
        self.assertEqual(result["lower"],[])
        self.assertEqual(result["higher"],[])
        self.assertEqual(len(result["pending"]),4)

    def test_change(self):
        items=[{"name":"Example habit","history":[{"day":"2026-01-15","status":"Ongoing","dose":""}]}]
        def read(day):
            return [{"name":"Fibromyalgia pain","answer":"Severe" if day<"2026-01-15" else "Mild"}]
        result=summarize(date(2026,1,30),items,read,lambda d:None)
        self.assertEqual(result["lower"][0]["symptom"],"Fibromyalgia pain")
        self.assertEqual(result["lower"][0]["before_n"],14)
        self.assertEqual(result["lower"][0]["after_n"],14)
