"""Shared counting rules for diary reports and period reviews."""
from favourite_feed.health_answers import QUESTIONS
from favourite_feed.health_impact import SCORES

# Translate explicit bleeding answers into shared report counter names.
BLEEDING_KEYS = {
    "Period": "period",
    "Spotting": "spotting",
    "Unexpected": "unexpected",
    "None": "no_bleeding",
}


# Return a numeric score only for severity and sleep questions; None means no usable score.
def severity_score(name, value):
    if QUESTIONS.get(name) in ("severity", "sleep"):
        return SCORES.get(value)
    return None


# Increment only the counter for an explicitly recorded bleeding answer.
def count_bleeding(counts, name, value):
    if name == "Period / bleeding today":
        key = BLEEDING_KEYS.get(value)
        if key:
            counts[key] += 1


# Count explicit rest days separately from active days and sum recorded session minutes; missing logs count as neither.
def count_exercise(counts, log):
    if log:
        if log["rest"]:
            counts["rest"] += 1
        elif log["sessions"]:
            counts["active"] += 1
            counts["minutes"] += sum(s["minutes"] for s in log["sessions"])
