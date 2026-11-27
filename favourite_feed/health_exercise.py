from datetime import timedelta
from statistics import mean
from favourite_feed.health_impact import SCORES
from favourite_feed.health_answers import QUESTIONS

# Use a dedicated record name to keep exercise logs separate from symptom answers for the same date.
KEY = "exercise-log-v1"
ACTIVITIES = ("Walking", "Cardio", "Strength", "Yoga / Pilates", "Other")


# Check the structure of the daily exercise log before it is saved.
def validate(data):
    if not isinstance(data, dict) or set(data) != {"rest", "sessions"}:
        raise ValueError("Invalid log")
    # A rest day must be explicitly recorded and cannot contain exercise sessions. Limit each day to 20 sessions.
    rest, sessions = data["rest"], data["sessions"]
    if type(rest) is not bool or not isinstance(sessions, list) or len(sessions) > 20 or (rest and sessions):
        raise ValueError("Invalid log")
    # Each session needs a supported activity, whole minutes between 1 and 1440, and a recognised intensity.
    for s in sessions:
        if not isinstance(s, dict) or set(s) != {"activity", "minutes", "intensity"}:
            raise ValueError("Invalid session")
        if s["activity"] not in ACTIVITIES or type(s["minutes"]) is not int or not 1 <= s["minutes"] <= 1440 or s["intensity"] not in ("Light", "Moderate", "High"):
            raise ValueError("Invalid session")
    return data


# Compare recorded symptom severity after exercise and rest days at the requested delay; this measures associations, not causes.
def compare_exercise(today, days, lag, read_exercise, read_symptoms):
    # Collect symptom scores separately for rest and active days; counts track recorded days, not individual answers.
    groups = {"rest": {}, "active": {}}
    counts = {"rest": 0, "active": 0}
    for offset in range(days):
        # Work backwards from today, shifting the activity date earlier by the selected lag.
        exposure = today - timedelta(days=offset + lag)
        log = read_exercise(exposure.isoformat())
        # Missing exercise information is not evidence of rest, so exclude it from the comparison.
        if not log:
            continue
        # An explicit rest flag means rest; a non-empty session list means active; otherwise skip the day.
        group = "rest" if log["rest"] else "active" if log["sessions"] else None
        if group is None:
            continue
        counts[group] += 1
        # Read symptoms on the outcome date, which is the activity date plus the chosen delay.
        for entry in read_symptoms((exposure + timedelta(days=lag)).isoformat()):
            name, answer = entry["name"], entry["answer"]
            # Only severity and sleep answers with recognised numeric scores contribute to averages.
            if QUESTIONS.get(name) in ("severity", "sleep") and answer in SCORES:
                groups[group].setdefault(name, []).append(SCORES[answer])
    rows = []
    # Include symptoms recorded in either group, even when the other group has no answers.
    for name in sorted(groups["rest"].keys() | groups["active"].keys()):
        a, b = groups["rest"].get(name, []), groups["active"].get(name, [])
        # Calculate each group's arithmetic mean, leaving missing averages as None rather than zero.
        x, y = mean(a) if a else None, mean(b) if b else None
        direction = "insufficient"
        # Require five recorded answers in each group before describing a difference of at least half a score point.
        if len(a) >= 5 and len(b) >= 5:
            direction = "lower" if y-x <= -.5 else "higher" if y-x >= .5 else "similar"
        # Return averages and sample sizes together so the browser can show how much evidence supports the comparison.
        rows.append(dict(name=name, rest=x, active=y, rest_n=len(a), active_n=len(b), direction=direction))
    return dict(rows=rows, counts=counts)
