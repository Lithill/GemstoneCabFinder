from datetime import timedelta
from statistics import mean
from favourite_feed.health_answers import QUESTIONS
from favourite_feed.health_impact import SCORES
from favourite_feed.health_ongoing import effective
from favourite_feed.health_exercise import compare_exercise


def build_report(today, days, items, read_day, read_exercise):
    start = today-timedelta(days=days-1)
    diary, exercise = {}, {}
    counts = dict(diary=0, active=0, rest=0, minutes=0, period=0, spotting=0, unexpected=0, no_bleeding=0)
    ratings, monthly, events = {}, {}, []
    for i in range(days):
        day = (start+timedelta(days=i)).isoformat()
        entries = diary[day] = read_day(day)
        log = exercise[day] = read_exercise(day)
        counts["diary"] += bool(entries)
        for e in entries:
            name, value = e["name"], e["answer"]
            if QUESTIONS.get(name) in ("severity","sleep") and value in SCORES:
                ratings.setdefault(name,[]).append(SCORES[value])
                monthly.setdefault(day[:7],{}).setdefault(name,[]).append(SCORES[value])
            elif name == "Period / bleeding today":
                key = {"Period":"period","Spotting":"spotting","Unexpected":"unexpected","None":"no_bleeding"}.get(value)
                if key:
                    counts[key] += 1
            elif name == "Period start or end date":
                events.append(dict(day=day,value=value,details=e["extras"]))
        if log:
            if log["rest"]:
                counts["rest"] += 1
            elif log["sessions"]:
                counts["active"] += 1
                counts["minutes"] += sum(s["minutes"] for s in log["sessions"])
    symptoms = [dict(name=name,mean=mean(v),n=len(v),severe=v.count(3),none=v.count(0)) for name,v in ratings.items()]
    symptoms.sort(key=lambda r:(-r["mean"],r["name"]))
    current = []
    changes = []
    for item in items:
        if item["category"] not in ("Medication","Supplement"):
            continue
        event = effective(item,today.isoformat())
        if event:
            current.append(dict(event,name=item["name"],category=item["category"]))
        changes.extend(dict(e,name=item["name"],category=item["category"]) for e in item["history"] if start.isoformat()<=e["day"]<=today.isoformat())
    # Use only days inside the report for both exposure and outcome.
    associations=[]
    for lag in (0,1,2,3):
        result=compare_exercise(today,days-lag,lag,exercise.get,lambda d:diary.get(d,[]))
        associations.extend(dict(r,lag=lag) for r in result["rows"] if r["direction"] in ("lower","higher"))
    associations.sort(key=lambda r:(-min(r["rest_n"],r["active_n"]),-abs(r["active"]-r["rest"])))
    return dict(start=start.isoformat(),end=today.isoformat(),days=days,counts=counts,symptoms=symptoms,
                current=current,changes=sorted(changes,key=lambda e:e["day"]),period_events=events,
                monthly=[dict(month=m,rows=[dict(name=n,mean=mean(v),n=len(v)) for n,v in sorted(rows.items())]) for m,rows in sorted(monthly.items())],
                associations=associations[:8])
