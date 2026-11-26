from datetime import timedelta
from functools import lru_cache
from statistics import mean
from favourite_feed.health_impact import SCORES
from favourite_feed.health_answers import QUESTIONS

GROUPS = {
    "intensity": ("Rest", "Light", "Moderate", "High"),
    "duration": ("Rest", "1–15 min", "16–30 min", "31–60 min", "61+ min"),
    "frequency": ("0–2 active days", "3–4 active days", "5–7 active days"),
    "recovery": ("Rest after exercise", "Exercise after rest", "Consecutive exercise"),
}


def activity(log):
    if not log:
        return None
    return "rest" if log["rest"] else "active" if log["sessions"] else None


def compare_recovery(today, days, lag, mode, symptom, read_exercise, read_symptoms):
    read_exercise = lru_cache(maxsize=100)(read_exercise)
    groups = {name: [] for name in GROUPS[mode]}
    counts = dict.fromkeys(groups, 0)
    for offset in range(days):
        outcome = today - timedelta(days=offset)
        exposure = outcome - timedelta(days=lag)
        log = read_exercise(exposure.isoformat())
        state = activity(log)
        if state is None:
            continue
        if mode == "intensity":
            group = "Rest" if state == "rest" else max(
                (s["intensity"] for s in log["sessions"]), key=("Light","Moderate","High").index)
        elif mode == "duration":
            minutes = sum(s["minutes"] for s in log["sessions"])
            group = "Rest" if state == "rest" else "1–15 min" if minutes <= 15 else "16–30 min" if minutes <= 30 else "31–60 min" if minutes <= 60 else "61+ min"
        elif mode == "frequency":
            week = [activity(read_exercise((exposure-timedelta(days=i)).isoformat())) for i in range(7)]
            if None in week:
                continue
            n = week.count("active")
            group = "0–2 active days" if n <= 2 else "3–4 active days" if n <= 4 else "5–7 active days"
        else:
            previous = activity(read_exercise((exposure-timedelta(days=1)).isoformat()))
            group = {("active","rest"):"Rest after exercise",("rest","active"):"Exercise after rest",("active","active"):"Consecutive exercise"}.get((previous,state))
            if group is None:
                continue
        counts[group] += 1
        for entry in read_symptoms(outcome.isoformat()):
            if entry["name"] == symptom and entry["answer"] in SCORES:
                groups[group].append(SCORES[entry["answer"]])
                break
    return [{"label":name,"mean":mean(values) if values else None,"n":len(values),"days":counts[name]} for name,values in groups.items()]
