"""Offline-only validation tests: no health routes or database writes."""
import math
import unittest
from favourite_feed.health_answers import QUESTIONS, validate_entry


class SymptomAnswerTests(unittest.TestCase):
    def test_all_current_question_types_are_covered(self):
        self.assertEqual(set(QUESTIONS.values()), {"yesno", "period", "date", "severity", "sleep", "uti", "libido", "weight"})
        self.assertEqual(len(QUESTIONS), 38)

    def test_valid_answers_are_canonical_and_do_not_mutate_input(self):
        samples = [
            ("Hot flushes", {"answer": "Yes"}),
            ("Brain fog", {"answer": "Moderate"}),
            ("Period / bleeding today", {"answer": "Period", "flow": "Heavy"}),
            ("Period / bleeding today", {"answer": "None"}),
            ("Period start or end date", {"answer": "2026-11-20", "detail": "Start"}),
            ("Difficulty sleeping / insomnia", {"answer": "Mild", "hours": 6.5}),
            ("UTI episode / recurrent UTIs", {"answer": "Suspected", "detail": "Test"}),
            ("Sex drive / low libido / fluctuations", {"answer": "Fluctuating"}),
            ("Weight measurement", {"answer": 65.4, "unit": "kg"}),
        ]
        for question, answer in samples:
            with self.subTest(question=question):
                result = validate_entry("2026-11-21", question, answer)
                self.assertEqual(result["answer"], answer)
                self.assertIsNot(result["answer"], answer)

    def test_invalid_answers_fail_closed(self):
        samples = [
            ("Not a symptom", {"answer": "Mild"}),
            ("Hot flushes", {"answer": "Maybe"}),
            ("Brain fog", {"answer": ""}),
            ("Brain fog", {"answer": "Mild", "notes": "secret"}),
            ("Period / bleeding today", {"answer": "None", "flow": "Heavy"}),
            ("Period / bleeding today", {"answer": "Period", "flow": "Invalid"}),
            ("Period start or end date", {"answer": "2026-02-30", "detail": "Start"}),
            ("Period start or end date", {"answer": "2026-11-20", "detail": "Other"}),
            ("Difficulty sleeping / insomnia", {"answer": "None", "hours": 25}),
            ("Difficulty sleeping / insomnia", {"answer": "None", "hours": float("nan")}),
            ("Weight measurement", {"answer": -1, "unit": "kg"}),
            ("Weight measurement", {"answer": float("inf"), "unit": "kg"}),
            ("Weight measurement", {"answer": True, "unit": "kg"}),
            ("Weight measurement", {"answer": 50, "unit": "invalid"}),
            ("UTI episode / recurrent UTIs", {"answer": "Resolved", "detail": "x" * 501}),
        ]
        for question, answer in samples:
            with self.subTest(question=question, answer=answer):
                with self.assertRaises(ValueError):
                    validate_entry("2026-11-21", question, answer)

    def test_invalid_entry_date_rejected(self):
        for day in ("not-a-date", "2026-02-30", "2026-1-2"):
            with self.subTest(day=day):
                with self.assertRaises(ValueError):
                    validate_entry(day, "Brain fog", {"answer": "Mild"})


if __name__ == "__main__":
    unittest.main()
