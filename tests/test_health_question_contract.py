"""Keep the non-saving browser questionnaire aligned with offline validation.

This reads the JavaScript source as text; it never runs browser code,
starts Flask, accesses a vault or processes real health information.
"""
from pathlib import Path
import re
import unittest

from favourite_feed.health_answers import QUESTIONS

ROOT = Path(__file__).resolve().parents[1]
TRACKER_JS = ROOT / "favourite_feed" / "static" / "symptom_tracker.js"


class HealthQuestionContractTests(unittest.TestCase):
    def test_question_names_and_types_match_browser_prototype(self):
        source = TRACKER_JS.read_text(encoding="utf-8")
        # Restrict parsing to the static groups declaration so unrelated UI
        # arrays and future dynamic code cannot silently become questions.
        start = source.index("const groups = [")
        end = source.index("const questions=", start)
        declaration = source[start:end]
        browser_questions = re.findall(
            r'\[\s*"([^"\\]+)"\s*,\s*"(yesno|period|date|severity|sleep|uti|libido|weight)"\s*\]',
            declaration,
        )
        self.assertEqual(len(browser_questions), 37)
        self.assertEqual(len(browser_questions), len(set(name for name, _ in browser_questions)))
        self.assertEqual(dict(browser_questions), QUESTIONS)

    def test_prototype_has_no_browser_storage_or_health_write_requests(self):
        source = TRACKER_JS.read_text(encoding="utf-8")
        for forbidden in ("localStorage", "sessionStorage", "indexedDB", "navigator.sendBeacon", "fetch(", "XMLHttpRequest"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
