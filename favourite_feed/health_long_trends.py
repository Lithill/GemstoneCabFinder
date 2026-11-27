from calendar import monthrange
from datetime import date
from statistics import mean
from favourite_feed.health_impact import SCORES


def monthly_trends(today, months, read_answer):
    rows = []
    # Process calendar months from oldest to newest.
    for offset in reversed(range(months)):
        # Convert a month offset into a year and month, including transitions across years.
        year, month = divmod(today.year*12+today.month-1-offset,12)
        month += 1
        # Use elapsed days for the current month and the actual calendar length for past months.
        total = today.day if (year,month)==(today.year,today.month) else monthrange(year,month)[1]
        scores = []
        for n in range(1,total+1):
            answer = read_answer(date(year,month,n).isoformat())
            # Exclude missing answers while retaining recorded zero severity.
            if answer is not None and answer["answer"] in SCORES:
                scores.append(SCORES[answer["answer"]])
        # Return average severity, answer count, days available, severe and symptom-free counts, and a current-month flag.
        rows.append(dict(month=f"{year:04d}-{month:02d}",mean=mean(scores) if scores else None,
                         n=len(scores),days=total,severe=scores.count(3),none=scores.count(0),
                         partial=(year,month)==(today.year,today.month)))
    return rows
