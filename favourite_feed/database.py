import sqlite3
from contextlib import contextmanager, closing
from pathlib import Path

# Resolve the project directory from this file rather than relying on the current working directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "favourite_feed.db"


# Provide a reusable database connection that commits successful work, rolls back errors and closes afterwards.
@contextmanager
def connect_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DB_PATH)) as conn:
        # Allow database rows to be accessed by column name, for example row["title"].
        conn.row_factory = sqlite3.Row
        # Enforce relationships between tables, such as a listing belonging to an existing shop.
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            yield conn


# Create missing gemstone tables and indexes without replacing existing records.
def setup_database():
    with connect_database() as conn:
        # Run the SQL schema: shops, imported name mappings, listings and their photos. Indexes help common searches.
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
            CREATE INDEX IF NOT EXISTS idx_listing_images_listing_rank ON listing_images(listing_id, image_rank);
            CREATE INDEX IF NOT EXISTS idx_listings_seen_published ON listings(published_at DESC, listing_id DESC) WHERE seen_at IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_listings_published
                ON listings(published_at DESC);
        """)


def ensure_shop_baseline(conn):
    """Upgrade older gemstone databases inside the caller's write transaction."""
    if "baseline_at" not in {row[1] for row in conn.execute("PRAGMA table_info(monitored_shops)")}:
        conn.execute("ALTER TABLE monitored_shops ADD COLUMN baseline_at TEXT")
        conn.execute("UPDATE monitored_shops SET baseline_at=last_checked WHERE last_checked IS NOT NULL")
