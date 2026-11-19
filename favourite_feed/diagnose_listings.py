"""Inspect listing ordering, timestamps, pagination and images without changing feed data."""
from datetime import datetime, timezone
import json

from favourite_feed.etsy_api import etsy_get


SHOPS = {"999GEMS": 30037649, "A2ZStones": 17921936, "AAjewelryIndonesia": 46474596}
TIMESTAMP_FIELDS = ("creation_timestamp", "created_timestamp",
                    "original_creation_timestamp", "last_modified_timestamp",
                    "updated_timestamp", "state_timestamp")


def display_timestamp(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc).isoformat()
    return value


def main():
    for name, shop_id in SHOPS.items():
        print(f"\n=== {name} ({shop_id}) ===", flush=True)
        endpoint = f"shops/{shop_id}/listings/active"
        for offset in (0, 5):
            data = etsy_get(endpoint, {
                "limit": 5, "offset": offset,
                "sort_on": "created", "sort_order": "desc",
            })
            print(f"Total: {data.get('count')}; offset: {offset}")
            listings = data["results"]
            for listing in listings:
                print(json.dumps({
                    "listing_id": listing["listing_id"],
                    "title": listing.get("title"),
                    "price": listing.get("price"),
                    **{key: display_timestamp(listing.get(key))
                       for key in TIMESTAMP_FIELDS},
                }, ensure_ascii=True))
            if offset == 0 and listings:
                listing_id = listings[0]["listing_id"]
                images = etsy_get(f"listings/{listing_id}/images")["results"]
                print(f"Images for {listing_id}: {len(images)}")
                for img in images[:3]:
                    print(json.dumps({
                        key: img.get(key) for key in (
                            "listing_image_id", "rank", "url_570xN",
                            "url_fullxfull", "full_width", "full_height")
                    }))
            if len(listings) < 5:
                break


if __name__ == "__main__":
    main()
