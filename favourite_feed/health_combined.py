from datetime import date, timedelta
from functools import lru_cache
from statistics import mean
from favourite_feed.health_impact import SCORES
from favourite_feed.health_recovery import activity

CONTEXTS = ("No bleeding", "Period", "Spotting / unexpected")
def compare_combined(today, days, lag, symptom, items, read_day, read_exercise):
    # Reuse diary reads within this calculation rather than maintaining a persistent decrypted cache.
    read_day = lru_cache(maxsize=100)(read_day)
    # Collect dated medication and supplement events up to today.
    events = sorted({date.fromisoformat(e["day"]) for item in items
                     if item["category"] in ("Medication", "Supplement")
                     for e in item["history"] if e["day"] <= today.isoformat()})
    # Create six contexts by combining three bleeding categories with presence or absence of a recent recorded change.
    groups = {(context, recent): {"active": [], "rest": []}
              for context in CONTEXTS for recent in (False, True)}
    # Track the first missing requirement that prevents each day from being compared.
    excluded = {"activity": 0, "bleeding": 0, "symptom": 0}
    for offset in range(days):
        outcome = today - timedelta(days=offset)
        exposure = outcome - timedelta(days=lag)
        state = activity(read_exercise(exposure.isoformat()))
        if state is None:
            excluded["activity"] += 1
            continue
        entries = {e["name"]:e["answer"] for e in read_day(outcome.isoformat())}
        context = {"None":CONTEXTS[0], "Period":CONTEXTS[1], "Spotting":CONTEXTS[2], "Unexpected":CONTEXTS[2]}.get(entries.get("Period / bleeding today"))
        if context is None:
            excluded["bleeding"] += 1
            continue
        # A recorded None severity has score zero; a missing symptom has no score.
        score = SCORES.get(entries.get(symptom))
        if score is None:
            excluded["symptom"] += 1
            continue
        # Flag events from 14 days before exposure through the outcome date; this does not establish a medication effect.
        recent = any(exposure-timedelta(days=14) <= e <= outcome for e in events)
        groups[context,recent][state].append(score)
    rows=[]
    for (context,recent), group in groups.items():
        a,b=group["rest"],group["active"]
        x,y=mean(a) if a else None,mean(b) if b else None
        direction="insufficient"
        # Require at least five scores in both activity groups before labelling the difference.
        if len(a)>=5 and len(b)>=5:
            direction="lower" if y-x<=-.5 else "higher" if y-x>=.5 else "similar"
        rows.append(dict(context=context,recent=recent,rest=x,active=y,rest_n=len(a),active_n=len(b),direction=direction))
    return dict(rows=rows,excluded=excluded)
