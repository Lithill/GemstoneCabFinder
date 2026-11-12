# Gemstone cabochon seller search settings
import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ETSY_API_KEY")
shared_secret = os.getenv("ETSY_SHARED_SECRET")

headers = {
    "x-api-key": f"{api_key}:{shared_secret}"
}

SEARCH_TERMS = [
    "gemstone cabochon",
    "natural stone cabochon",
    "loose gemstone cabochon",
]

TARGET_COUNTRIES = [
    "India",
    "United States",
    "Indonesia",
    "United Kingdom",
]

MIN_SHOP_AGE_DAYS = 365
MIN_SHOP_RATING = 4.5
MIN_SHOP_REVIEWS = 20

print("\nGemstone seller search settings loaded.")
print("Target countries:", ", ".join(TARGET_COUNTRIES))
print("Minimum shop age:", MIN_SHOP_AGE_DAYS, "days")
print("Minimum rating:", MIN_SHOP_RATING)
print("Minimum reviews:", MIN_SHOP_REVIEWS)

# First gemstone cabochon search

search_url = "https://openapi.etsy.com/v3/application/listings/active"

search_params = {
    "keywords": SEARCH_TERMS[0],
    "limit": 100,
}

print("\nSearching Etsy for:", SEARCH_TERMS[0])

try:
    response = requests.get(
        search_url,
        headers=headers,
        params=search_params,
        timeout=30
    )

    print("Search HTTP status:", response.status_code)

    if response.status_code == 200:
        data = response.json()
        listings = data.get("results", [])
        # Keep only listings mentioning cabochons
        cabochon_listings = []

        for listing in listings:
            title = listing.get("title", "").lower()

            excluded_words = [
                "necklace",
                "choker",
                "bracelet",
                "pendant with chain",
                "finished jewelry",
                "finished jewellery",
            ]

            is_cabochon = "cabochon" in title
            is_finished_jewelry = any(
                word in title for word in excluded_words
            )

            if is_cabochon and not is_finished_jewelry:
                cabochon_listings.append(listing)

        listings = cabochon_listings

        print("Cabochon listings after filtering:", len(listings))

        print("Total matching listings:", data.get("count", 0))
        print("Listings returned:", len(listings))

        for listing in listings:
            print("\nTitle:", listing.get("title"))
            print("Shop ID:", listing.get("shop_id"))
            print("URL:", listing.get("url"))
        # Collect unique shops from the search results
        unique_shop_ids = set()

        for listing in listings:
            shop_id = listing.get("shop_id")

            if shop_id:
                unique_shop_ids.add(shop_id)

        print("\nUnique shops found:", len(unique_shop_ids))

        for shop_id in sorted(unique_shop_ids):
            print("Shop ID:", shop_id)

        # Check every unique shop
        qualifying_shops = []

        for shop_id in sorted(unique_shop_ids):
            shop_url = f"https://openapi.etsy.com/v3/application/shops/{shop_id}"

            shop_response = requests.get(
                shop_url,
                headers=headers,
                timeout=30
            )

            if shop_response.status_code != 200:
                print("Could not retrieve shop:", shop_id)
                continue

            shop = shop_response.json()

            shop_name = shop.get("shop_name")
            rating = shop.get("review_average")
            reviews = shop.get("review_count")

            print(f"\nChecking: {shop_name}")
            print("Rating:", rating)
            print("Reviews:", reviews)

            if rating is None or reviews is None:
                print("Result: EXCLUDED - missing review information")
                continue

            # Check rating, reviews and shop age
            from datetime import datetime, timezone

            created_timestamp = shop.get("create_date")

            if created_timestamp is None:
                print("Result: EXCLUDED - missing shop creation date")
                continue

            created_date = datetime.fromtimestamp(
                created_timestamp,
                tz=timezone.utc
            )

            shop_age_days = (
                datetime.now(timezone.utc) - created_date
            ).days

            print("Shop age:", shop_age_days, "days")

            if (
                rating >= MIN_SHOP_RATING
                and reviews >= MIN_SHOP_REVIEWS
                and shop_age_days >= MIN_SHOP_AGE_DAYS
            ):
                print("Result: PASSED all three checks")
                qualifying_shops.append(shop)
            else:
                print("Result: EXCLUDED")

        print("\n" + "=" * 40)
        print("Shops passing rating, reviews and age checks:", len(qualifying_shops))

        # Filter shops by shipping-from country
        TARGET_SHIPPING_COUNTRIES = {"IN", "US", "ID", "GB"}

        final_shops = []
        unknown_shipping_shops = []

        print("\nChecking shipping countries:")

        for shop in qualifying_shops:
            shop_name = shop.get("shop_name")
            shipping_country = shop.get("shipping_from_country_iso")

            print(f"\nShop: {shop_name}")
            print("Ships from:", shipping_country)

            if shipping_country in TARGET_SHIPPING_COUNTRIES:
                final_shops.append(shop)
                print("Result: PASSED shipping country check")

            elif not shipping_country:
                unknown_shipping_shops.append(shop)
                print("Result: UNKNOWN shipping country")

            else:
                print("Result: EXCLUDED - ships from another country")

        print("\n" + "=" * 40)
        print("FINAL QUALIFYING SHOPS:", len(final_shops))
        print("Shops with unknown shipping country:",
              len(unknown_shipping_shops))

        for shop in final_shops:
            print("Qualified:", shop.get("shop_name"))
        # Export qualifying shops to Excel
        excel_rows = []

        for shop in final_shops:
            excel_rows.append({
                "Shop Name": shop.get("shop_name"),
                "Shop ID": shop.get("shop_id"),
                "Ships From": shop.get("shipping_from_country_iso"),
                "Rating": shop.get("review_average"),
                "Reviews": shop.get("review_count"),
                "Shop URL": shop.get("url"),
            })

        df = pd.DataFrame(excel_rows)

        output_file = "gemstone_sellers.xlsx"
        df.to_excel(output_file, index=False)

        print("\nExcel file created:", output_file)
        print("Shops exported:", len(df))

    else:
        print("Search unsuccessful.")
        print("Response:", response.text[:500])

except requests.RequestException as error:
    print("Search error:", error)