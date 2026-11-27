"""Read-only diagnostic for Etsy listings missing from the feed.

Run: python -m favourite_feed.diagnose_missing 4597851686 4620868361
"""
import argparse
from datetime import datetime, timezone, timedelta
from favourite_feed.database import connect_database, setup_database
from favourite_feed.etsy_api import etsy_get
from favourite_feed.refresh import inclusion_reason, OVERLAP

# Format available timestamps in UTC and label missing values.
def timestamp(value):
    return datetime.fromtimestamp(int(value), timezone.utc).isoformat() if value else "unavailable"

# Accept listing IDs and inspect live Etsy data alongside local feed records.
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("listing_ids", type=int, nargs="+")
    args = parser.parse_args()
    # Ensure schema exists; despite the read-only diagnostic purpose this can initialise database tables.
    setup_database()
    for lid in args.listing_ids:
        print("\nListing", lid, flush=True)
        try:
            item = etsy_get(f"listings/{lid}")
            # Check whether the seller is monitored and whether the listing is already stored.
            with connect_database() as conn:
                shop = conn.execute("SELECT * FROM monitored_shops WHERE shop_id=?", (item.get("shop_id"),)).fetchone()
                saved = conn.execute("SELECT seen_at, liked FROM listings WHERE listing_id=?", (lid,)).fetchone()
            print("Title:", item.get("title"))
            print("Shop monitored:", shop["shop_name"] if shop else "NO")
            print("Saved:", dict(saved) if saved else "NO")
            for key in ("original_creation_timestamp", "creation_timestamp", "state_timestamp"):
                print(key + ":", timestamp(item.get(key)))
            # Reconstruct the current refresh window and evaluate the shared inclusion rule without importing the listing.
            if shop and shop["last_checked"]:
                baseline = int(datetime.fromisoformat(shop["baseline_at"] or shop["last_checked"]).timestamp())
                cutoff = int((datetime.fromisoformat(shop["last_checked"]) - OVERLAP).timestamp())
                upper = int(datetime.now(timezone.utc).timestamp())
                print("Baseline:", timestamp(baseline))
                print("Last checked:", shop["last_checked"])
                print("Current rule:", inclusion_reason(item, baseline, cutoff, upper))
            else:
                print("No baseline established")
        except Exception as exc:
            print("Error:", type(exc).__name__, str(exc)[:300])
if __name__ == "__main__":
    main()
