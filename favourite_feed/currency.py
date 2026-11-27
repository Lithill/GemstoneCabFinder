"""Indicative GBP prices; rates from the free open exchange-rate endpoint."""
import json
import math
import time
import requests
from favourite_feed.database import connect_database

# Read the saved exchange rates and their download time from SQLite.
def cached_rates():
    with connect_database() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS currency_cache (id INTEGER PRIMARY KEY, fetched REAL, rates TEXT)")
        row = conn.execute("SELECT fetched, rates FROM currency_cache WHERE id=1").fetchone()
    return (row[0], json.loads(row[1])) if row else (0, {})

# Reuse rates less than a day old; otherwise request fresh GBP-based rates.
def update_rates():
    fetched, rates = cached_rates()
    if rates and time.time()-fetched < 86400:
        return True
    try:
        response = requests.get("https://open.er-api.com/v6/latest/GBP", timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("result") != "success" or data.get("base_code") != "GBP":
            return False
        # Reject invalid, infinite or non-positive exchange rates before caching.
        rates = {k: v for k, v in data["rates"].items() if isinstance(v, (int, float)) and math.isfinite(v) and v > 0}
        if len(rates) < 2:
            return False
        with connect_database() as conn:
            conn.execute("INSERT OR REPLACE INTO currency_cache VALUES (1, ?, ?)", (time.time(), json.dumps(rates)))
        return True
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return False

# Return a formatting function that templates can use for each listing's price.
def price_context():
    fetched, rates = cached_rates()
    def display(item):
        if not item["price_divisor"] or item["price_amount"] is None:
            return ("", "")
        # Etsy supplies an integer price and a divisor, for example 1250 divided by 100 is 12.50.
        amount = item["price_amount"]/item["price_divisor"]
        code = item["currency_code"] or ""
        original = f"{amount:,.2f} {code}"
        if code == "GBP":
            return (f"£{amount:,.2f}", "")
        # Divide by the GBP-based exchange rate to estimate pounds, using rates less than seven days old.
        if code in rates and time.time()-fetched < 7*86400:
            return (f"≈ £{amount/rates[code]:,.2f}", original)
        return (original, "GBP rate unavailable")
    return display
