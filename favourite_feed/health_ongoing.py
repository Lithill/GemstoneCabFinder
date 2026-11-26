from datetime import date

CATEGORIES = ("Medication", "Supplement", "Exercise", "Diet", "Other")
STATUSES = ("Taking", "Tapering", "Withdrawal", "Ongoing", "Stopped")
KEY_DAY = "0001-01-01"
KEY_QUESTION = "ongoing-factors-v1"


def validate(items):
    if not isinstance(items, list) or len(items) > 20:
        raise ValueError("Invalid factors")
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"name", "category", "history"}:
            raise ValueError("Invalid factor")
        name = item["name"]
        if not isinstance(name, str) or not name.strip() or len(name) > 100 or name.casefold() in seen:
            raise ValueError("Invalid name")
        seen.add(name.casefold())
        if item["category"] not in CATEGORIES:
            raise ValueError("Invalid category")
        history = item["history"]
        if not isinstance(history, list) or not 1 <= len(history) <= 100:
            raise ValueError("Invalid history")
        dates = set()
        for event in history:
            if not isinstance(event, dict) or set(event) != {"day", "status", "dose"}:
                raise ValueError("Invalid event")
            day = event["day"]
            if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day or day in dates:
                raise ValueError("Invalid date")
            dates.add(day)
            if event["status"] not in STATUSES or not isinstance(event["dose"], str) or len(event["dose"]) > 100:
                raise ValueError("Invalid status or dose")
    return items


def effective(item, day):
    return max((e for e in item["history"] if e["day"] <= day),
               key=lambda e: e["day"], default=None)
