import argparse
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from favourite_feed.database import PROJECT_ROOT, connect_database, setup_database
from favourite_feed.etsy_api import find_shop_by_name

SOURCE_DB = PROJECT_ROOT / "data" / "gemstone_sellers.db"
FAVOURITES_FILE = PROJECT_ROOT / "data" / "favourited_shops.txt"


def load_favourite_names():
    names = set()
    with closing(sqlite3.connect(SOURCE_DB.as_uri() + "?mode=ro", uri=True)) as conn:
        for (name,) in conn.execute("SELECT shop_name FROM favourite_shops"):
            if name and name.strip():
                names.add(name.strip())
    with FAVOURITES_FILE.open(encoding="utf-8-sig") as file:
        for line in file:
            name = line.strip()
            if name and not name.startswith("#"):
                names.add(name)
    return sorted(names)


def save_shop(source_name, shop):
    with connect_database() as conn:
        conn.execute("""
            INSERT INTO monitored_shops (shop_id, shop_name, shop_url, added_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(shop_id) DO UPDATE SET
                shop_name=excluded.shop_name, shop_url=excluded.shop_url
        """, (shop["shop_id"], shop["shop_name"],
              "https://www.etsy.com/shop/" + shop["shop_name"],
              datetime.now(timezone.utc).isoformat()))
        conn.execute("""
            INSERT INTO shop_name_mappings (source_name, shop_id)
            VALUES (?, ?)
            ON CONFLICT(source_name) DO UPDATE SET shop_id=excluded.shop_id
        """, (source_name, shop["shop_id"]))


def sync_favourites(limit=None):
    names = load_favourite_names()
    setup_database()
    with connect_database() as conn:
        resolved = {row[0] for row in conn.execute(
            "SELECT source_name FROM shop_name_mappings"
        )}
    pending = [name for name in names if name not in resolved]
    print("Favourite shop names:", len(names))
    print("Already resolved:", len(set(names) & resolved))
    print("Awaiting lookup:", len(pending))
    if limit is not None:
        pending = pending[:limit]
    print("Shops to look up this run:", len(pending))
    unmatched = []
    failed = False
    for index, name in enumerate(pending, 1):
        print(f"[{index}/{len(pending)}] Looking up {name}", flush=True)
        try:
            shop = find_shop_by_name(name)
            if shop is None:
                unmatched.append(name)
                print("  No unique exact match found.")
                continue
            save_shop(name, shop)
            print("  Shop ID:", shop["shop_id"], "| Verified name:", shop["shop_name"])
        except Exception as error:
            print(f"  Lookup failed: {error}")
            print("  Stopping sync. Saved progress retained.")
            failed = True
            break
    with connect_database() as conn:
        count = conn.execute("SELECT COUNT(*) FROM monitored_shops").fetchone()[0]
    print("Total unique monitored shops:", count)
    print("Unmatched names this run:", len(unmatched))
    for name in unmatched:
        print(" ", name)
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    raise SystemExit(sync_favourites(args.limit))
