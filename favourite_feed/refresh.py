"""Manual refresh of favourite shops; first check establishes a baseline."""
import argparse
import html
from datetime import datetime, timezone, timedelta
from favourite_feed.database import connect_database, setup_database
from favourite_feed.etsy_api import etsy_get

PAGE_SIZE = 100
OVERLAP = timedelta(minutes=10)


def refresh_shop(shop):
    shop_id = shop["shop_id"]
    started = datetime.now(timezone.utc)
    if not shop["last_checked"]:
        with connect_database() as conn:
            conn.execute("UPDATE monitored_shops SET last_checked=? WHERE shop_id=?",
                         (started.isoformat(), shop_id))
        return "Baseline established (no backlog)"
    cutoff = int((datetime.fromisoformat(shop["last_checked"]) - OVERLAP).timestamp())
    upper = int(started.timestamp())
    offset = 0
    candidates = {}
    while True:
        data = etsy_get(f"shops/{shop_id}/listings/active", {
            "limit": PAGE_SIZE, "offset": offset,
            "sort_on": "created", "sort_order": "desc",
        })
        rows = data["results"]
        if not rows:
            break
        for item in rows:
            original = int(item["original_creation_timestamp"])
            if cutoff <= original <= upper:
                candidates[item["listing_id"]] = item
        offset += len(rows)
        if offset >= data["count"] or int(rows[-1]["creation_timestamp"]) < cutoff:
            break
    with connect_database() as conn:
        known = {row[0] for row in conn.execute(
            "SELECT listing_id FROM listings WHERE shop_id=?", (shop_id,))}
    # Do not import pre-baseline listings merely because of the overlap.
    # For subsequent checks the overlap may recover delayed API results.
    with connect_database() as conn:
        baseline = conn.execute("SELECT added_at FROM monitored_shops WHERE shop_id=?",
                                (shop_id,)).fetchone()[0]
    new_count = 0
    for listing_id, item in candidates.items():
        if listing_id in known or item["original_creation_timestamp"] < datetime.fromisoformat(baseline).timestamp():
            continue
        images = etsy_get(f"listings/{listing_id}/images")["results"]
        price = item.get("price") or {}
        with connect_database() as conn:
            result = conn.execute("""
                INSERT INTO listings (listing_id, shop_id, title, description,
                    listing_url, price_amount, price_divisor, currency_code,
                    published_at, discovered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(listing_id) DO NOTHING
            """, (listing_id, shop_id, html.unescape(item["title"]),
                  html.unescape(item.get("description") or ""), item.get("url"),
                  price.get("amount"), price.get("divisor"), price.get("currency_code"),
                  item["original_creation_timestamp"], started.isoformat()))
            if result.rowcount:
                for image in images:
                    url = image.get("url_fullxfull") or image.get("url_570xN")
                    if url:
                        conn.execute("""INSERT OR IGNORE INTO listing_images
                            (image_id, listing_id, image_url, image_rank) VALUES (?, ?, ?, ?)""",
                            (image["listing_image_id"], listing_id, url, image.get("rank")))
                new_count += 1
    with connect_database() as conn:
        conn.execute("UPDATE monitored_shops SET last_checked=? WHERE shop_id=?",
                     (started.isoformat(), shop_id))
    return f"{new_count} new listings"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--shop", action="append", help="Exact shop name; repeat to select multiple shops")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    setup_database()
    with connect_database() as conn:
        shops = conn.execute("SELECT * FROM monitored_shops WHERE is_active=1 ORDER BY shop_id").fetchall()
    if args.shop:
        shops = [shop for shop in shops if shop["shop_name"] in args.shop]
        missing = set(args.shop) - {shop["shop_name"] for shop in shops}
        if missing:
            parser.error("Unknown active shops: " + ", ".join(sorted(missing)))
    shops = shops[:args.limit]
    failures = []
    for i, shop in enumerate(shops, 1):
        print(f"[{i}/{len(shops)}] {shop['shop_name']}", flush=True)
        try:
            print(" ", refresh_shop(shop), flush=True)
        except Exception as exc:
            failures.append(shop["shop_name"])
            print("  Failed:", exc, flush=True)
            if "rate limit" in str(exc).lower():
                break
    print("Failed shops:", failures)
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
