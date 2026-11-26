from datetime import timedelta
from statistics import mean
from favourite_feed.health_impact import SCORES
from favourite_feed.health_answers import QUESTIONS

KEY = "exercise-log-v1"
ACTIVITIES = ("Walking", "Cardio", "Strength", "Yoga / Pilates", "Other")


def validate(data):
    if not isinstance(data, dict) or set(data) != {"rest", "sessions"}:
        raise ValueError("Invalid log")
    rest, sessions = data["rest"], data["sessions"]
    if type(rest) is not bool or not isinstance(sessions, list) or len(sessions) > 20 or (rest and sessions):
        raise ValueError("Invalid log")
    for s in sessions:
        if not isinstance(s, dict) or set(s) != {"activity", "minutes", "intensity"}:
            raise ValueError("Invalid session")
        if s["activity"] not in ACTIVITIES or type(s["minutes"]) is not int or not 1 <= s["minutes"] <= 1440 or s["intensity"] not in ("Light", "Moderate", "High"):
            raise ValueError("Invalid session")
    return data


def compare_exercise(today, days, lag, read_exercise, read_symptoms):
    groups = {"rest": {}, "active": {}}
    counts = {"rest": 0, "active": 0}
    for offset in range(days):
        exposure = today - timedelta(days=offset + lag)
        log = read_exercise(exposure.isoformat())
        if not log:
            continue
        group = "rest" if log["rest"] else "active" if log["sessions"] else None
        if group is None:
            continue
        counts[group] += 1
        for entry in read_symptoms((exposure + timedelta(days=lag)).isoformat()):
            name, answer = entry["name"], entry["answer"]
            if QUESTIONS.get(name) in ("severity", "sleep") and answer in SCORES:
                groups[group].setdefault(name, []).append(SCORES[answer])
    rows = []
    for name in sorted(groups["rest"].keys() | groups["active"].keys()):
        a, b = groups["rest"].get(name, []), groups["active"].get(name, [])
        x, y = mean(a) if a else None, mean(b) if b else None
        direction = "insufficient"
        if len(a) >= 5 and len(b) >= 5:
            direction = "lower" if y-x <= -.5 else "higher" if y-x >= .5 else "similar"
        rows.append(dict(name=name, rest=x, active=y, rest_n=len(a), active_n=len(b), direction=direction))
    return dict(rows=rows, counts=counts)
