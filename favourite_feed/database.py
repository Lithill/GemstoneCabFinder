import sqlite3
from contextlib import contextmanager, closing
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "favourite_feed.db"


@contextmanager
def connect_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            yield conn


def setup_database():
    with connect_database() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS monitored_shops (
                shop_id INTEGER PRIMARY KEY,
                shop_name TEXT NOT NULL,
                shop_url TEXT NOT NULL,
                added_at TEXT NOT NULL,
                last_checked TEXT,
                is_active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS shop_name_mappings (
                source_name TEXT PRIMARY KEY COLLATE BINARY,
                shop_id INTEGER NOT NULL REFERENCES monitored_shops(shop_id)
            );
            CREATE TABLE IF NOT EXISTS listings (
                listing_id INTEGER PRIMARY KEY,
                shop_id INTEGER NOT NULL REFERENCES monitored_shops(shop_id),
                title TEXT NOT NULL,
                description TEXT,
                listing_url TEXT,
                price_amount INTEGER,
                price_divisor INTEGER,
                currency_code TEXT,
                published_at INTEGER NOT NULL,
                discovered_at TEXT NOT NULL,
                seen_at TEXT,
                liked INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS listing_images (
                image_id INTEGER PRIMARY KEY,
                listing_id INTEGER NOT NULL REFERENCES listings(listing_id),
                image_url TEXT NOT NULL,
                image_rank INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_listings_published
                ON listings(published_at DESC);
        """)
