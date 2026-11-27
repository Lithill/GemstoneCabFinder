from datetime import timedelta
from functools import lru_cache
from statistics import mean
from favourite_feed.health_impact import SCORES
from favourite_feed.health_answers import QUESTIONS

# Define the available ways to group exercise exposure days.
GROUPS = {
    "intensity": ("Rest", "Light", "Moderate", "High"),
    "duration": ("Rest", "1–15 min", "16–30 min", "31–60 min", "61+ min"),
    "frequency": ("0–2 active days", "3–4 active days", "5–7 active days"),
    "recovery": ("Rest after exercise", "Exercise after rest", "Consecutive exercise"),
}


# Distinguish explicit rest and active days from missing or empty logs.
def activity(log):
    if not log:
        return None
    return "rest" if log["rest"] else "active" if log["sessions"] else None


def compare_recovery(today, days, lag, mode, symptom, read_exercise, read_symptoms):
    # Cache repeated reads during this calculation only, particularly for overlapping seven-day windows.
    read_exercise = lru_cache(maxsize=100)(read_exercise)
    groups = {name: [] for name in GROUPS[mode]}
    counts = dict.fromkeys(groups, 0)
    for offset in range(days):
        outcome = today - timedelta(days=offset)
        # Look back by the selected lag from the symptom outcome date.
        exposure = outcome - timedelta(days=lag)
        log = read_exercise(exposure.isoformat())
        state = activity(log)
        if state is None:
            continue
        # Classify an active day by its highest recorded session intensity.
        if mode == "intensity":
            group = "Rest" if state == "rest" else max(
                (s["intensity"] for s in log["sessions"]), key=("Light","Moderate","High").index)
        # Add all session minutes and assign the total to a duration band.
        elif mode == "duration":
            minutes = sum(s["minutes"] for s in log["sessions"])
            group = "Rest" if state == "rest" else "1–15 min" if minutes <= 15 else "16–30 min" if minutes <= 30 else "31–60 min" if minutes <= 60 else "61+ min"
        # Count active days in the seven-day window ending on the exposure date; require all seven days to be recorded.
        elif mode == "frequency":
            week = [activity(read_exercise((exposure-timedelta(days=i)).isoformat())) for i in range(7)]
            if None in week:
                continue
            n = week.count("active")
            group = "0–2 active days" if n <= 2 else "3–4 active days" if n <= 4 else "5–7 active days"
        else:
            # Compare consecutive recorded activity states; missing states and consecutive rest are excluded.
            previous = activity(read_exercise((exposure-timedelta(days=1)).isoformat()))
            group = {("active","rest"):"Rest after exercise",("rest","active"):"Exercise after rest",("active","active"):"Consecutive exercise"}.get((previous,state))
            if group is None:
                continue
        # Count qualifying exposure days separately from days with a recorded symptom score.
        counts[group] += 1
        for entry in read_symptoms(outcome.isoformat()):
            if entry["name"] == symptom and entry["answer"] in SCORES:
                groups[group].append(SCORES[entry["answer"]])
                break
    return [{"label":name,"mean":mean(values) if values else None,"n":len(values),"days":counts[name]} for name,values in groups.items()]
