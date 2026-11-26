"""Manual refresh of favourite shops; first check establishes a baseline."""
import argparse
import html
from datetime import datetime, timezone, timedelta
from favourite_feed.database import connect_database, setup_database
from favourite_feed.etsy_api import etsy_get

PAGE_SIZE = 100
OVERLAP = timedelta(hours=24)
ACTIVATION_WINDOW_SECONDS = 120

def inclusion_reason(item, baseline, cutoff, upper):
    """Conservative signal for newly activated drafts; not proof of publication."""
    original = int(item.get("original_creation_timestamp") or 0)
    created = int(item.get("creation_timestamp") or 0)
    state = int(item.get("state_timestamp") or 0)
    if not cutoff <= created <= upper:
        return "outside scan window"
    if baseline <= original <= upper:
        return "original creation after baseline"
    if baseline <= state <= upper and abs(state - created) <= ACTIVATION_WINDOW_SECONDS:
        return "possible draft publication: activation matches creation"
    return "older original creation; no matching activation (possible renewal)"


def store_listing(shop_id, item, published_at, started):
    listing_id = item["listing_id"]
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
              published_at, started.isoformat()))
        if result.rowcount:
            for image in images:
                url = image.get("url_fullxfull") or image.get("url_570xN")
                if url:
                    conn.execute("""INSERT OR IGNORE INTO listing_images
                        (image_id, listing_id, image_url, image_rank) VALUES (?, ?, ?, ?)""",
                        (image["listing_image_id"], listing_id, url, image.get("rank")))
            return 1
    return 0


def refresh_shop(shop):
    shop_id = shop["shop_id"]
    started = datetime.now(timezone.utc)
    with connect_database() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if "baseline_at" not in {r[1] for r in conn.execute("PRAGMA table_info(monitored_shops)")}:
            conn.execute("ALTER TABLE monitored_shops ADD COLUMN baseline_at TEXT")
            conn.execute("UPDATE monitored_shops SET baseline_at=last_checked WHERE last_checked IS NOT NULL")
    if not shop["last_checked"]:
        with connect_database() as conn:
            conn.execute("UPDATE monitored_shops SET last_checked=?, baseline_at=? WHERE shop_id=?",
                         (started.isoformat(), started.isoformat(), shop_id))
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
            created = int(item.get("creation_timestamp") or 0)
            if cutoff <= created <= upper:
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
        baseline = conn.execute("SELECT baseline_at FROM monitored_shops WHERE shop_id=?",
                                (shop_id,)).fetchone()[0]
    baseline_ts = int(datetime.fromisoformat(baseline).timestamp())
    new_count = 0
    for listing_id, item in candidates.items():
        reason = inclusion_reason(item, baseline_ts, cutoff, upper)
        if listing_id in known or reason.startswith(("outside", "older")):
            continue
        published_at = item["state_timestamp"] if int(item.get("original_creation_timestamp") or 0) < baseline_ts else item["original_creation_timestamp"]
        new_count += store_listing(shop_id, item, published_at, started)
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
