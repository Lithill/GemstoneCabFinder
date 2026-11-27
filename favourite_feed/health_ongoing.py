from datetime import date

# Define supported ongoing-factor categories and the statuses available for dated changes.
CATEGORIES = ("Medication", "Supplement", "Exercise", "Diet", "Other")
STATUSES = ("Taking", "Tapering", "Withdrawal", "Ongoing", "Stopped")
# Use a reserved date and record name to store the whole ongoing-factor collection independently of daily diary entries.
KEY_DAY = "0001-01-01"
KEY_QUESTION = "ongoing-factors-v1"


# Validate the complete collection before saving it, allowing up to 20 ongoing factors.
def validate(items):
    if not isinstance(items, list) or len(items) > 20:
        raise ValueError("Invalid factors")
    # Track names without case differences so the same factor cannot be entered twice with different capitalisation.
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
        # Each factor has a history of one to 100 dated events rather than just its latest status.
        history = item["history"]
        if not isinstance(history, list) or not 1 <= len(history) <= 100:
            raise ValueError("Invalid history")
        # Require unique canonical dates within each factor's history so only one event applies per day.
        dates = set()
        for event in history:
            if not isinstance(event, dict) or set(event) != {"day", "status", "dose"}:
                raise ValueError("Invalid event")
            day = event["day"]
            if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day or day in dates:
                raise ValueError("Invalid date")
            dates.add(day)
            # Check the status against the supported choices and bound the length of the free-text dose.
            if event["status"] not in STATUSES or not isinstance(event["dose"], str) or len(event["dose"]) > 100:
                raise ValueError("Invalid status or dose")
    return items


# Find the most recent event on or before the requested date; return None if the factor had not yet been recorded.
def effective(item, day):
    return max((e for e in item["history"] if e["day"] <= day),
               key=lambda e: e["day"], default=None)
