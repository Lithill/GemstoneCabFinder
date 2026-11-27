import re
from urllib.parse import urlsplit
from datetime import datetime, timezone
from favourite_feed.database import ensure_shop_baseline, connect_database
from favourite_feed.etsy_api import etsy_get, find_shop_by_name
from favourite_feed.refresh import store_listing


# Accept an exact Etsy shop name or extract it from a valid HTTPS Etsy shop URL.
def shop_name(value):
    value = value.strip()
    if "://" in value:
        url = urlsplit(value)
        if url.scheme != "https" or url.netloc.lower() not in ("etsy.com","www.etsy.com"):
            raise ValueError("Use an Etsy shop URL or exact shop name.")
        match = re.fullmatch(r"/(?:[a-z]{2}/)?shop/([A-Za-z0-9]+)/?",url.path)
        if not match:
            raise ValueError("Use an Etsy shop URL, not a listing URL.")
        value = match.group(1)
    if not re.fullmatch(r"[A-Za-z0-9]{1,40}",value):
        raise ValueError("Enter an exact Etsy shop name.")
    return value


# Look up the exact seller and add it to monitoring without overwriting an existing record.
def add_shop(value, *, expected_id=None):
    name = shop_name(value)
    shop = find_shop_by_name(name)
    if not shop:
        raise ValueError("No exact Etsy shop match found. Check the spelling and capitalisation.")
    sid = int(shop["shop_id"])
    # During discovery review, verify that the name still refers to the seller originally selected.
    if expected_id is not None and sid != expected_id:
        raise ValueError("Shop identity changed.")
    now = datetime.now(timezone.utc).isoformat()
    with connect_database() as conn:
        conn.execute("BEGIN IMMEDIATE")
        # Ensure older databases support the baseline date; new shops start monitoring from now.
        ensure_shop_baseline(conn)
        result = conn.execute("""INSERT INTO monitored_shops
            (shop_id,shop_name,shop_url,added_at,last_checked,baseline_at,is_active)
            VALUES (?,?,?,?,?,?,1) ON CONFLICT(shop_id) DO NOTHING""",
            (sid,shop["shop_name"],"https://www.etsy.com/shop/"+name,now,now,now))
        created = bool(result.rowcount)
    return sid, created


# Explicitly import a small number of recent active listings, including those from before monitoring began.
def import_recent(sid, limit):
    if limit not in (5,10,20):
        raise ValueError("Invalid import limit.")
    with connect_database() as conn:
        if not conn.execute("SELECT 1 FROM monitored_shops WHERE shop_id=?",(sid,)).fetchone():
            raise ValueError("Unknown shop.")
        # Collect existing listing IDs so imports can be repeated without duplicating saved stones.
        known = {r[0] for r in conn.execute("SELECT listing_id FROM listings WHERE shop_id=?",(sid,))}
    now = datetime.now(timezone.utc)
    rows = etsy_get(f"shops/{sid}/listings/active",{"limit":limit,"sort_on":"created","sort_order":"desc"})["results"]
    count = 0
    for item in rows[:limit]:
        if item["listing_id"] in known:
            continue
        published = int(item.get("original_creation_timestamp") or item.get("creation_timestamp") or 0)
        count += store_listing(sid,item,published,now)
    return count
