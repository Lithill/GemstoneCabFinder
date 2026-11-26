from datetime import timedelta
from functools import lru_cache
from favourite_feed.health_impact import compare
from favourite_feed.health_exercise import compare_exercise


def summarize(today, items, read_day, read_exercise):
    read_day = lru_cache(maxsize=120)(read_day)
    read_exercise = lru_cache(maxsize=100)(read_exercise)
    events = sorted([dict(e, name=i["name"]) for i in items for e in i["history"]
                     if e["day"] <= today.isoformat()], key=lambda e: e["day"], reverse=True)
    findings, pending = [], []
    def collect(label, rows, a, b, overlap=False):
        eligible = [r for r in rows if r["direction"] != "insufficient"]
        if not eligible:
            pending.append(label)
            return
        for r in eligible:
            if r["direction"] in ("lower", "higher"):
                findings.append(dict(factor=label, symptom=r["name"], direction=r["direction"],
                    before=r[a], after=r[b], before_n=r[a+"_n"], after_n=r[b+"_n"], overlap=overlap))
    from datetime import date
    for event in events[:5]:
        change = date.fromisoformat(event["day"])
        label = event["name"] + " — " + event["day"] + " (" + event["status"] + ")"
        if change < today - timedelta(days=90):
            continue
        if change.toordinal() <= 14:
            continue
        overlap = sum(abs((date.fromisoformat(e["day"])-change).days)<=14 for e in events)>1
        collect(label, compare(change,14,today,read_day), "before","after",overlap)
    for lag in (0,1,2,3):
        label = "Exercise — " + ("same day" if lag==0 else "next day" if lag==1 else str(lag)+" days later")
        collect(label,compare_exercise(today,30,lag,read_exercise,read_day)["rows"],"rest","active")
    # Keep one finding per exercise symptom and direction; show the largest sample first.
    findings.sort(key=lambda r: (-min(r["before_n"],r["after_n"]),-abs(r["after"]-r["before"]),r["factor"],r["symptom"]))
    seen=set()
    unique=[]
    for r in findings:
        key=("Exercise" if r["factor"].startswith("Exercise — ") else r["factor"],r["symptom"],r["direction"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return {"lower":[r for r in unique if r["direction"]=="lower"][:5],
            "higher":[r for r in unique if r["direction"]=="higher"][:5],
            "pending":pending}
