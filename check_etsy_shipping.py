
import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ETSY_API_KEY")
shared_secret = os.getenv("ETSY_SHARED_SECRET")

if not api_key or not shared_secret:
    raise SystemExit("Missing Etsy API credentials in .env")

headers = {
    "x-api-key": f"{api_key}:{shared_secret}"
}

url = "https://openapi.etsy.com/v3/application/listings/active"

response = requests.get(
    url,
    headers=headers,
    params={
        "keywords": "dendritic agate cabochon",
        "limit": 1,
    },
    timeout=30,
)

print("HTTP status:", response.status_code)

if response.status_code != 200:
    print("API error:", response.text[:300])
    raise SystemExit(1)

results = response.json().get("results", [])

if not results:
    raise SystemExit("No listings returned")

listing = results[0]

print("\nListing ID:", listing.get("listing_id"))
print("Shop ID:", listing.get("shop_id"))

print("\nShipping-related fields:")
for key, value in listing.items():
    if any(word in key.lower() for word in (
        "shipping", "delivery", "postage",
        "destination", "currency", "rare"
    )):
        print(f"{key}: {value}")

print("\nShipping profile ID:", listing.get("shipping_profile_id"))
