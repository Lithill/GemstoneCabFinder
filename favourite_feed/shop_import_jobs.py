"""Small, resumable shop imports; each request processes at most five listings."""
import json
from datetime import datetime, timezone
from favourite_feed.database import connect_database
from favourite_feed.etsy_api import etsy_get
from favourite_feed.refresh import store_listing


def setup(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS shop_import_jobs (
        shop_id INTEGER PRIMARY KEY, offset INTEGER NOT NULL DEFAULT 0,
        pending TEXT NOT NULL DEFAULT '[]', total INTEGER,
        processed INTEGER NOT NULL DEFAULT 0, imported INTEGER NOT NULL DEFAULT 0,
        skipped INTEGER NOT NULL DEFAULT 0, done INTEGER NOT NULL DEFAULT 0,
        last_page INTEGER NOT NULL DEFAULT 0)""")


def start(sid):
    # Resume an unfinished job; a completed job can be explicitly started again.
    with connect_database() as conn:
        setup(conn)
        if not conn.execute("SELECT 1 FROM monitored_shops WHERE shop_id=?", (sid,)).fetchone():
            raise ValueError("Unknown shop.")
        conn.execute("DELETE FROM shop_import_jobs WHERE shop_id=? AND done=1", (sid,))
        conn.execute("INSERT OR IGNORE INTO shop_import_jobs(shop_id) VALUES (?)", (sid,))


def status(sid):
    with connect_database() as conn:
        setup(conn)
        row = conn.execute("SELECT * FROM shop_import_jobs WHERE shop_id=?", (sid,)).fetchone()
        if not row:
            raise ValueError("No import started.")
        return {key: row[key] for key in ("total","processed","imported","skipped","done")}


def step(sid):
    # Save each fetched page before importing its items so interrupted requests can resume.
    with connect_database() as conn:
        setup(conn)
        row = conn.execute("SELECT * FROM shop_import_jobs WHERE shop_id=?", (sid,)).fetchone()
    if not row:
        raise ValueError("No import started.")
    if row["done"]:
        return status(sid)
    pending = json.loads(row["pending"])
    if not pending and not row["last_page"]:
        page = etsy_get(f"shops/{sid}/listings/active", {"limit":100,"offset":row["offset"],"sort_on":"created","sort_order":"desc"})
        pending = page["results"]
        with connect_database() as conn:
            conn.execute("UPDATE shop_import_jobs SET pending=?,offset=?,total=?,last_page=? WHERE shop_id=?",
                         (json.dumps(pending),row["offset"]+len(pending),page.get("count"),int(len(pending)<100),sid))
    for item in pending[:5]:
        with connect_database() as conn:
            known = conn.execute("SELECT 1 FROM listings WHERE listing_id=?", (item["listing_id"],)).fetchone()
        added = 0
        if not known:
            published = int(item.get("original_creation_timestamp") or item.get("creation_timestamp") or 0)
            added = store_listing(sid,item,published,datetime.now(timezone.utc))
        # A successful listing is durable before advancing the queue. Retries skip existing IDs.
        pending.pop(0)
        with connect_database() as conn:
            conn.execute("UPDATE shop_import_jobs SET pending=?,processed=processed+1,imported=imported+?,skipped=skipped+? WHERE shop_id=?",
                         (json.dumps(pending),added,1-added,sid))
    with connect_database() as conn:
        conn.execute("UPDATE shop_import_jobs SET done=1 WHERE shop_id=? AND pending='[]' AND last_page=1", (sid,))
    return status(sid)


# List the latest saved import for each shop without making any Etsy requests.
def list_jobs():
    with connect_database() as conn:
        setup(conn)
        return conn.execute("""SELECT j.shop_id, s.shop_name, j.total, j.processed,
            j.imported, j.skipped, j.done FROM shop_import_jobs j
            JOIN monitored_shops s ON s.shop_id=j.shop_id
            ORDER BY j.done, s.shop_name COLLATE NOCASE""").fetchall()
