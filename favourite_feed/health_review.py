from datetime import timedelta
from statistics import mean
from favourite_feed.health_summary import severity_score, count_bleeding, count_exercise


def review(today, days, items, read_day, read_exercise):
    periods = []
    for shift in (days, 0):
        end = today - timedelta(days=shift+1)
        start = end - timedelta(days=days-1)
        ratings = {}
        counts = dict(diary_days=0, active=0, rest=0, minutes=0, period=0, spotting=0, unexpected=0, no_bleeding=0)
        for i in range(days):
            day = (start+timedelta(days=i)).isoformat()
            entries = read_day(day)
            counts["diary_days"] += bool(entries)
            for e in entries:
                name, value = e["name"], e["answer"]
                score = severity_score(name, value)
                if score is not None:
                    ratings.setdefault(name, []).append(score)
                count_bleeding(counts, name, value)
            log = read_exercise(day)
            count_exercise(counts, log)
        changes = sorted([dict(e,name=item["name"]) for item in items for e in item["history"]
                          if start.isoformat() <= e["day"] <= end.isoformat()],key=lambda e:e["day"])
        periods.append(dict(start=start.isoformat(),end=end.isoformat(),counts=counts,changes=changes,ratings=ratings))
    a,b=periods
    rows=[]
    minimum=3 if days==7 else 5
    for name in sorted(a["ratings"].keys() | b["ratings"].keys()):
        x,y=a["ratings"].get(name,[]),b["ratings"].get(name,[])
        before,after=mean(x) if x else None,mean(y) if y else None
        direction="insufficient"
        if len(x)>=minimum and len(y)>=minimum:
            direction="lower" if after-before<=-.5 else "higher" if after-before>=.5 else "similar"
        rows.append(dict(name=name,before=before,after=after,before_n=len(x),after_n=len(y),direction=direction))
    for p in periods:
        del p["ratings"]
    return dict(previous=a,current=b,rows=rows,minimum=minimum)
