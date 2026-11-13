
import csv
import sqlite3
from pathlib import Path

DB_PATH = Path("data/gemstone_sellers.db")
CSV_PATH = Path("data/etsy_favourites_complete.csv")

with sqlite3.connect(DB_PATH) as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS favourite_shops (
            shop_name TEXT PRIMARY KEY COLLATE NOCASE,
            shop_url TEXT NOT NULL
        )
    """)

    with CSV_PATH.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            name = row["name"].strip()
            url = row["url"].strip()

            if name and url:
                conn.execute("""
                    INSERT INTO favourite_shops
                        (shop_name, shop_url)
                    VALUES (?, ?)
                    ON CONFLICT(shop_name) DO UPDATE SET
                        shop_url = excluded.shop_url
                """, (name, url))

    count = conn.execute(
        "SELECT COUNT(*) FROM favourite_shops"
    ).fetchone()[0]

print(f"Favourite shops in database: {count}")
