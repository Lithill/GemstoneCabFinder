"""Populate a separate demo database and launch the local preview."""
from datetime import datetime, timezone
import html
from favourite_feed import database
from favourite_feed.etsy_api import etsy_get


def main():
    database.DB_PATH = database.PROJECT_ROOT / "data" / "favourite_feed_demo.db"
    database.setup_database()
    now = datetime.now(timezone.utc).isoformat()
    for shop_id, name in [(30037649, "999GEMS"), (17921936, "A2ZStones"),
                          (46474596, "AAjewelryIndonesia")]:
        with database.connect_database() as conn:
            conn.execute("""INSERT OR IGNORE INTO monitored_shops
                (shop_id, shop_name, shop_url, added_at) VALUES (?, ?, ?, ?)""",
                (shop_id, name, "https://www.etsy.com/shop/" + name, now))
        data = etsy_get(f"shops/{shop_id}/listings/active", {
            "limit": 6, "sort_on": "created", "sort_order": "desc"})
        for item in data["results"]:
            lid = item["listing_id"]
            with database.connect_database() as conn:
                if conn.execute("SELECT 1 FROM listings WHERE listing_id=?", (lid,)).fetchone():
                    continue
            images = etsy_get(f"listings/{lid}/images")["results"]
            price = item.get("price") or {}
            with database.connect_database() as conn:
                conn.execute("""INSERT INTO listings
                    (listing_id, shop_id, title, description, listing_url,
                    price_amount, price_divisor, currency_code, published_at, discovered_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (lid, shop_id, html.unescape(item["title"]),
                     html.unescape(item.get("description") or ""), item.get("url"),
                     price.get("amount"), price.get("divisor"), price.get("currency_code"),
                     item["original_creation_timestamp"], now))
                for img in images:
                    url = img.get("url_fullxfull") or img.get("url_570xN")
                    if url:
                        conn.execute("""INSERT OR IGNORE INTO listing_images
                            (image_id, listing_id, image_url, image_rank)
                            VALUES (?, ?, ?, ?)""",
                            (img["listing_image_id"], lid, url, img.get("rank")))
    from favourite_feed.web import app
    print("DEMO only: http://127.0.0.1:5001", flush=True)
    app.run(host="127.0.0.1", port=5001, debug=False)


if __name__ == "__main__":
    main()
