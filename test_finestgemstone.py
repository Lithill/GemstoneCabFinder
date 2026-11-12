
import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ETSY_API_KEY")
shared_secret = os.getenv("ETSY_SHARED_SECRET")

url = "https://openapi.etsy.com/v3/application/listings/active"
headers = {
    "x-api-key": f"{api_key}:{shared_secret}"
}

search_terms = [
    "dendritic agate cabochon",
    "shazar dendritic agate",
    "agate cabochon",
]

for term in search_terms:
    print(f"\nSearching for: {term}")

    response = requests.get(
        url,
        headers=headers,
        params={
            "keywords": term,
            "limit": 100,
            "sort_on": "score",
        },
        timeout=30,
    )

    print("HTTP status:", response.status_code)

    if response.status_code != 200:
        print(response.text[:500])
        continue

    listings = response.json().get("results", [])

    print("Listings returned:", len(listings))

    matches = [
        listing for listing in listings
        if "shazar" in (listing.get("title") or "").casefold()
    ]

    print("Listings mentioning Shazar:", len(matches))

    for listing in matches[:5]:
        print(" ", listing.get("title"))
        print("  Shop ID:", listing.get("shop_id"))

    print("\nChecking shop ID 14333472...")

shop_url = "https://openapi.etsy.com/v3/application/shops/14333472"

response = requests.get(
    shop_url,
    headers=headers,
    timeout=30,
)

print("HTTP status:", response.status_code)

if response.status_code == 200:
    shop = response.json()
    print("Shop name:", shop.get("shop_name"))
    print("Shop ID:", shop.get("shop_id"))
else:
    print(response.text[:500])
