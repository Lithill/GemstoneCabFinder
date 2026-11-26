from datetime import date, timedelta
from statistics import mean
from favourite_feed.health_impact import SCORES

GROUPS = ("Week before start", "Recorded period", "Week after start (no bleeding)", "Other recorded no-bleeding days", "Spotting / unexpected bleeding")


def compare_cycle(today, days, symptom, read_day):
    first = today - timedelta(days=days-1)
    records = {}
    starts = set()
    for offset in range(-7, days):
        day = first + timedelta(days=offset)
        entries = read_day(day.isoformat())
        records[day] = {e["name"]: e["answer"] for e in entries}
        for e in entries:
            if e["name"] == "Period start or end date" and "detail: Start" in e["extras"]:
                start = date.fromisoformat(e["answer"])
                if first-timedelta(days=7) <= start <= today:
                    starts.add(start)
    for day, record in records.items():
        previous = records.get(day-timedelta(days=1), {})
        if record.get("Period / bleeding today") == "Period" and previous.get("Period / bleeding today") == "None":
            starts.add(day)
    groups = {name: [] for name in GROUPS}
    counts = dict.fromkeys(GROUPS, 0)
    for day, record in records.items():
        if day < first:
            continue
        bleeding = record.get("Period / bleeding today")
        if bleeding == "Period":
            group = GROUPS[1]
        elif bleeding in ("Spotting", "Unexpected"):
            group = GROUPS[4]
        elif bleeding == "None":
            before = any(1 <= (start-day).days <= 7 for start in starts)
            after = any(1 <= (day-start).days <= 7 for start in starts)
            if before and after or day in starts:
                continue
            group = GROUPS[0] if before else GROUPS[2] if after else GROUPS[3]
        else:
            continue
        counts[group] += 1
        value = record.get(symptom)
        if value in SCORES:
            groups[group].append(SCORES[value])
    return {"starts": sorted(d.isoformat() for d in starts if d >= first),
            "rows": [{"label": name, "mean": mean(values) if values else None,
                      "n": len(values), "days": counts[name]} for name, values in groups.items()]}
