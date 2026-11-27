from datetime import timedelta
from statistics import mean
from favourite_feed.health_summary import severity_score, count_bleeding, count_exercise
from favourite_feed.health_ongoing import effective
from favourite_feed.health_exercise import compare_exercise


def build_report(today, days, items, read_day, read_exercise):
    # Include today and the preceding days in the requested report window.
    start = today-timedelta(days=days-1)
    # Keep records in memory for reuse by the exercise comparisons within this report.
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
            score = severity_score(name, value)
            # Collect valid severity scores both for the entire report and for each calendar month.
            if score is not None:
                ratings.setdefault(name,[]).append(score)
                monthly.setdefault(day[:7],{}).setdefault(name,[]).append(score)
            count_bleeding(counts, name, value)
            # Keep explicitly entered period events separately from daily bleeding counts.
            if name == "Period start or end date":
                events.append(dict(day=day,value=value,details=e["extras"]))
        count_exercise(counts, log)
    # Summarise each symptom using its recorded answers only.
    symptoms = [dict(name=name,mean=mean(v),n=len(v),severe=v.count(3),none=v.count(0)) for name,v in ratings.items()]
    # Display highest mean severity first, using the name to break ties.
    symptoms.sort(key=lambda r:(-r["mean"],r["name"]))
    current = []
    changes = []
    for item in items:
        if item["category"] not in ("Medication","Supplement"):
            continue
        # Find the latest effective medication or supplement status as of today.
        event = effective(item,today.isoformat())
        if event:
            current.append(dict(event,name=item["name"],category=item["category"]))
        changes.extend(dict(e,name=item["name"],category=item["category"]) for e in item["history"] if start.isoformat()<=e["day"]<=today.isoformat())
    # Use only days inside the report for both exposure and outcome.
    associations=[]
    # Compare exercise and rest at each delay, shortening the outcome window to keep exposure dates inside the report.
    for lag in (0,1,2,3):
        result=compare_exercise(today,days-lag,lag,exercise.get,lambda d:diary.get(d,[]))
        associations.extend(dict(r,lag=lag) for r in result["rows"] if r["direction"] in ("lower","higher"))
    # Prioritise comparisons with larger minimum sample sizes, then larger absolute differences.
    associations.sort(key=lambda r:(-min(r["rest_n"],r["active_n"]),-abs(r["active"]-r["rest"])))
    return dict(start=start.isoformat(),end=today.isoformat(),days=days,counts=counts,symptoms=symptoms,
                current=current,changes=sorted(changes,key=lambda e:e["day"]),period_events=events,
                monthly=[dict(month=m,rows=[dict(name=n,mean=mean(v),n=len(v)) for n,v in sorted(rows.items())]) for m,rows in sorted(monthly.items())],
                associations=associations[:8])
