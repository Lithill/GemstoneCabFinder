from datetime import date, timedelta
from statistics import mean
from favourite_feed.health_answers import QUESTIONS

# Convert ordered severity choices to numbers for descriptive averages; missing answers are not zero.
SCORES = {"None": 0, "Mild": 1, "Moderate": 2, "Severe": 3}


def compare(change, window, today, read_day):
    # Collect recorded scores separately on either side of the selected change.
    before, after = {}, {}
    for offset in range(-window, window + 1):
        # Exclude the change day itself and skip future dates.
        if offset == 0:
            continue
        day = change + timedelta(days=offset)
        if day > today:
            continue
        # Negative offsets belong to the before period; positive offsets belong to the after period.
        target = before if offset < 0 else after
        for entry in read_day(day.isoformat()):
            name, answer = entry["name"], entry["answer"]
            if QUESTIONS.get(name) in {"severity", "sleep"} and answer in SCORES:
                target.setdefault(name, []).append(SCORES[answer])
    rows = []
    for name in sorted(before.keys() | after.keys()):
        a, b = before.get(name, []), after.get(name, [])
        # Calculate means only where answers exist.
        x, y = mean(a) if a else None, mean(b) if b else None
        direction = "insufficient"
        # Require five answers on each side; a difference of half a point or more is labelled higher or lower, not proof of causation.
        if len(a) >= 5 and len(b) >= 5:
            delta = y - x
            direction = "lower" if delta <= -0.5 else "higher" if delta >= 0.5 else "similar"
        rows.append(dict(name=name, before=x, after=y, before_n=len(a), after_n=len(b), direction=direction))
    return rows
