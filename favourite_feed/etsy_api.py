import os
import time

import requests
from dotenv import load_dotenv

from favourite_feed.database import PROJECT_ROOT

BASE_URL = "https://openapi.etsy.com/v3/application"
REQUEST_INTERVAL = 0.4


def get_headers():
    load_dotenv(PROJECT_ROOT / ".env")
    key = os.getenv("ETSY_API_KEY")
    secret = os.getenv("ETSY_SHARED_SECRET")
    if not key or not secret:
        raise RuntimeError("Etsy API credentials are missing.")
    return {"x-api-key": f"{key}:{secret}"}


def etsy_get(endpoint, params=None):
    headers = get_headers()
    for attempt in range(3):
        time.sleep(REQUEST_INTERVAL)
        try:
            response = requests.get(
                f"{BASE_URL}/{endpoint.lstrip('/')}",
                headers=headers, params=params, timeout=30
            )
        except (requests.Timeout, requests.ConnectionError):
            if attempt == 2:
                raise
            time.sleep(5)
            continue
        if response.status_code == 429:
            raise RuntimeError("Etsy API rate limit reached; stopping.")
        if response.status_code >= 500 and attempt < 2:
            time.sleep(5)
            continue
        response.raise_for_status()
        return response.json()


def find_shop_by_name(shop_name):
    offset = 0
    matches = {}
    while True:
        data = etsy_get("shops", {
            "shop_name": shop_name, "limit": 100, "offset": offset
        })
        results = data["results"]
        for shop in results:
            if shop.get("shop_name") == shop_name:
                matches[shop["shop_id"]] = shop
        offset += len(results)
        if not results or offset >= data["count"]:
            break
    return next(iter(matches.values())) if len(matches) == 1 else None
