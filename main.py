# Gemstone cabochon seller search settings
import sqlite3
from datetime import datetime, timezone, timedelta
import os
import re
import requests
import pandas as pd
from dotenv import load_dotenv
from config import (
    GEMSTONES,
    SEARCH_TERMS,
    TARGET_COUNTRIES,
    FINISHED_JEWELLERY_TERMS,
    WYSIWYG_POSITIVE_PHRASES,
    WYSIWYG_NEGATIVE_PHRASES,
    SHOP_CACHE_DAYS,
    MIN_SHOP_AGE_DAYS,
    MIN_SHOP_RATING,
    MIN_SHOP_REVIEWS,
    MAX_LISTINGS_TO_SEARCH,
    MAX_SHOP_LISTINGS_TO_SEARCH,
    TARGET_SHIPPING_COUNTRIES,
)

# Load shops that should be excluded from search results
def load_excluded_shops(filename="data/excluded_shops.txt"):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return {
                line.strip().casefold()
                for line in file
                if line.strip() and not line.strip().startswith("#")
            }
    except FileNotFoundError:
        print("Exclusion file not found. Continuing without exclusions.")
        return set()

def classify_wysiwyg(title, description=""):
    text = (title + " " + description).casefold()

    # Check for wording suggesting random stones
    for phrase in WYSIWYG_NEGATIVE_PHRASES:
        if phrase in text:
            return "Likely random selection"

    # Check for wording confirming the photographed stone
    for phrase in WYSIWYG_POSITIVE_PHRASES:
        if phrase in text:
            return "Likely WYSIWYG"

    # Not enough information to decide
    return "Needs checking"

def contains_listed_gemstone(title):
    title = title.casefold()

    return any(
        re.search(r"\b" + re.escape(gemstone.casefold()) + r"\b", title)
        for gemstone in GEMSTONES
    )

def is_loose_cabochon(title):
    title = title.casefold()

    if "cabochon" not in title and "cabochons" not in title:
        return False

    # Phrases suggesting the listing sells loose stones
    loose_stone_phrases = [
        "loose",
        "flat back",
        "flatback",
        "calibrated",
        "for jewelry making",
        "for jewellery making",
        "jewelry supply",
        "jewellery supply",
        "gemstone lot",
        "cabochon lot",
    ]

    # Remove loose-stone phrases before checking jewellery terms.
    # This protects phrases such as "for ring making".
    if "for ring making" in title:
        title = title.replace("for ring making", "")

    if "for pendant making" in title:
        title = title.replace("for pendant making", "")

    # Check for clear evidence that the listing sells loose stones
    is_loose_stone = any(
        phrase in title for phrase in loose_stone_phrases
    )

    # Check whether the title mentions finished jewellery
    is_finished_jewellery = any(
        re.search(r"\b" + re.escape(term) + r"\b", title)
        for term in FINISHED_JEWELLERY_TERMS
    )

    # Keep listings clearly described as loose stones
    if is_loose_stone:
        return True

    # Exclude listings mentioning finished jewellery
    if is_finished_jewellery:
        return False

    return True

def load_saved_shops():
    connection = sqlite3.connect("data/gemstone_sellers.db")

    rows = connection.execute("""
        SELECT shop_id, shop_name, last_checked, rating, review_count, shop_age_days, shipping_country
        FROM shops
    """).fetchall()

    connection.close()

    return [
        {
            "shop_id": row[0],
            "shop_name": row[1],
            "last_checked": row[2],
            "rating": row[3],
            "review_count": row[4],
            "shop_age_days": row[5],
            "shipping_country": row[6]
        }
        for row in rows
    ]

def save_shop_to_database(shop):

    created_timestamp = shop.get("create_date")

    shop_age_days = None
    if created_timestamp is not None:
        created_date = datetime.fromtimestamp(
            created_timestamp, tz=timezone.utc
        )
        shop_age_days = (
            datetime.now(timezone.utc) - created_date
        ).days

    connection = sqlite3.connect("data/gemstone_sellers.db")

    connection.execute("""
        INSERT INTO shops (
            shop_id, shop_name, rating, review_count,
            shop_age_days, shipping_country, last_checked
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(shop_id) DO UPDATE SET
            shop_name = excluded.shop_name,
            rating = excluded.rating,
            review_count = excluded.review_count,
            shop_age_days = excluded.shop_age_days,
            shipping_country = excluded.shipping_country,
            last_checked = excluded.last_checked
    """, (
        shop.get("shop_id"),
        shop.get("shop_name"),
        shop.get("review_average"),
        shop.get("review_count"),
        shop_age_days,
        shop.get("shipping_from_country_iso"),
        datetime.now(timezone.utc).isoformat()
    ))

    connection.commit()
    connection.close()

def main():
    """Run the Etsy gemstone cabochon seller search."""

    print("\nGemstone seller search settings loaded.")
    print("Target countries:", ", ".join(TARGET_COUNTRIES))
    print("Minimum shop age:", MIN_SHOP_AGE_DAYS, "days")
    print("Minimum rating:", MIN_SHOP_RATING)
    print("Minimum reviews:", MIN_SHOP_REVIEWS)

    load_dotenv()

    api_key = os.getenv("ETSY_API_KEY")
    shared_secret = os.getenv("ETSY_SHARED_SECRET")

    headers = {
        "x-api-key": f"{api_key}:{shared_secret}"
    }

    excluded_shops = load_excluded_shops()
    print("Excluded shops loaded:", len(excluded_shops))

    saved_shops = load_saved_shops()

    saved_shops_by_id = {
        shop["shop_id"]: shop
        for shop in saved_shops
    }

    print(f"Shops loaded from database: {len(saved_shops)}")

    # First gemstone cabochon search

    search_url = "https://openapi.etsy.com/v3/application/listings/active"

    try:
        all_listings = []
        seen_listing_ids = set()
        seen_search_shop_ids = set()
        batch_size = 100

        for search_term in SEARCH_TERMS:
            print(f"\nSearching Etsy for: {search_term}")

            search_params = {
                "keywords": search_term,
                "limit": batch_size,
                "offset": 0,
                "sort_on": "score",
            }

            for offset in range(0, MAX_LISTINGS_TO_SEARCH, batch_size):
                search_params["offset"] = offset

                response = requests.get(
                    search_url,
                    headers=headers,
                    params=search_params,
                    timeout=30
                )

                print(
                    f"  Batch {offset // batch_size + 1} HTTP status:",
                    response.status_code
                )

                if response.status_code != 200:
                    print("  Search batch failed:", response.text[:500])
                    break

                batch_listings = response.json().get("results", [])

                new_listings = 0

                for listing in batch_listings:
                    listing_id = listing.get("listing_id")

                    if listing_id is not None and listing_id not in seen_listing_ids:
                        seen_listing_ids.add(listing_id)
                        all_listings.append(listing)
                        new_listings += 1

                print("  New unique listings in batch:", new_listings)

                new_shops = 0

                for listing in batch_listings:
                    shop_id = listing.get("shop_id")

                    if shop_id is not None and shop_id not in seen_search_shop_ids:
                        seen_search_shop_ids.add(shop_id)
                        new_shops += 1

                print("  New shops discovered in batch:", new_shops)
                print("  Total shops discovered so far:", len(seen_search_shop_ids))
                print("  Total unique listings:", len(all_listings))

                if len(batch_listings) < batch_size:
                    break

        print("\nTOTAL UNIQUE MARKETPLACE LISTINGS:", len(all_listings))

        if all_listings:

            # Keep loose gemstone cabochons and exclude finished jewellery
            cabochon_listings = [
                listing
                for listing in all_listings
                if is_loose_cabochon(listing.get("title") or "")
                and contains_listed_gemstone(listing.get("title") or "")
            ]

            listings = cabochon_listings

            print("Cabochon listings after filtering:", len(listings))
            print("Total matching listings:", len(all_listings))
            print("Listings returned:", len(listings))

            for listing in listings:
                title = listing.get("title") or ""
                description = listing.get("description") or ""

                print("Description available:", bool(description))

                wysiwyg_status = classify_wysiwyg(title, description)

                listing["wysiwyg_status"] = wysiwyg_status

                print("\nTitle:", title)
                print("WYSIWYG:", wysiwyg_status)
                matched_phrases = [
                    phrase
                    for phrase in WYSIWYG_POSITIVE_PHRASES + WYSIWYG_NEGATIVE_PHRASES
                    if phrase in (title + " " + description).casefold()
                ]

                print("Matched WYSIWYG phrases:", matched_phrases)
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

            shops_to_check = unique_shop_ids | {
                shop["shop_id"] for shop in saved_shops
            }

            for shop_id in sorted(shops_to_check):
                cached_shop = saved_shops_by_id.get(shop_id)
                last_checked = (
                    cached_shop.get("last_checked")
                    if cached_shop
                    else None
                )
                cache_is_fresh = False

                if last_checked:
                    checked_date = datetime.fromisoformat(last_checked)
                    cache_is_fresh = (
                        datetime.now(timezone.utc) - checked_date
                        < timedelta(days=SHOP_CACHE_DAYS)
                    )
                cache_has_required_data = (
                    cached_shop is not None
                    and all(
                        cached_shop.get(field) is not None
                        for field in (
                            "shop_name",
                            "rating",
                            "review_count",
                            "shop_age_days",
                            "shipping_country",
                        )
                    )
                )
                use_cached_shop = cache_is_fresh and cache_has_required_data
                if use_cached_shop:
                    print(f"Cache available for shop ID: {shop_id}")
                    cached_shop_data = {
                        "shop_id": cached_shop["shop_id"],
                        "shop_name": cached_shop["shop_name"],
                        "review_average": cached_shop["rating"],
                        "review_count": cached_shop["review_count"],
                        "shipping_from_country_iso": cached_shop["shipping_country"],
                        "url": f"https://www.etsy.com/shop/{cached_shop['shop_name']}",
                        "_from_cache": True,
                    }
                    if cached_shop["shop_name"].casefold() not in excluded_shops:
                        qualifying_shops.append(cached_shop_data)
                    continue

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

                # Exclude shops already listed in excluded_shops.txt
                if shop_name and shop_name.casefold() in excluded_shops:
                    print(f"\nSkipping excluded shop: {shop_name}")
                    continue

                print(f"\nChecking: {shop_name}")
                print("Rating:", rating)
                print("Reviews:", reviews)

                if rating is None or reviews is None:
                    print("Result: EXCLUDED - missing review information")
                    continue

                # Check rating, reviews and shop age

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

                    if not shop.get("_from_cache"):
                        save_shop_to_database(shop)

                    print("Result: PASSED shipping country check")

                elif not shipping_country:
                    unknown_shipping_shops.append(shop)
                    print("Result: UNKNOWN shipping country")

                else:
                    print("Result: EXCLUDED - ships from another country")

            # Store listings retrieved directly from qualifying shops
            all_shop_listings = []

            # Retrieve active listings from every qualifying shop
            for shop in final_shops:
                shop_id = shop.get("shop_id")
                shop_name = shop.get("shop_name")

                print(f"\nRetrieving inventory for: {shop_name}")

                shop_listings_url = (
                    f"https://openapi.etsy.com/v3/application/shops/"
                    f"{shop_id}/listings/active"
                )

                shop_listing_count = 0

                for offset in range(0, MAX_SHOP_LISTINGS_TO_SEARCH, 100):
                    shop_response = requests.get(
                        shop_listings_url,
                        headers=headers,
                        params={"limit": 100, "offset": offset},
                        timeout=30
                    )

                    print(f"  Batch offset {offset}: HTTP",
                        shop_response.status_code)

                    if shop_response.status_code != 200:
                        print("  Inventory request failed:",
                            shop_response.text[:200])
                        break

                    batch = shop_response.json().get("results", [])

                    all_shop_listings.extend(batch)
                    shop_listing_count += len(batch)

                    if len(batch) < 100:
                        break

                print(f"  Listings retrieved: {shop_listing_count}")

            print("\nTOTAL SHOP INVENTORY LISTINGS RETRIEVED:",
                len(all_shop_listings))

            # Keep only loose cabochons containing a gemstone from our list
            cabochon_shop_listings = [
                listing
                for listing in all_shop_listings
                if is_loose_cabochon(listing.get("title") or "")
                and contains_listed_gemstone(listing.get("title") or "")
            ]

            print("LOOSE CABOCHON LISTINGS FOUND:",
                len(cabochon_shop_listings))

            # Classify WYSIWYG status for shop inventory listings
            wysiwyg_counts = {
                "Likely WYSIWYG": 0,
                "Needs checking": 0,
                "Likely random selection": 0,
            }

            for listing in cabochon_shop_listings:
                title = listing.get("title") or ""
                description = listing.get("description") or ""

                status = classify_wysiwyg(title, description)
                listing["wysiwyg_status"] = status

                wysiwyg_counts[status] += 1

            print("\nWYSIWYG CLASSIFICATION RESULTS:")
            for status, count in wysiwyg_counts.items():
                print(f"  {status}: {count}")

            print("\n" + "=" * 40)

            current_shop_ids = {shop["shop_id"] for shop in final_shops}

            missing_saved_shops = [
                shop for shop in saved_shops
                if shop["shop_id"] not in current_shop_ids
            ]

            missing_shop_ids = [
                shop["shop_id"] for shop in missing_saved_shops
            ]

            print("Saved shop IDs needing refresh:", missing_shop_ids)

            print("Previously saved shops not found this run:")
            for shop in missing_saved_shops:
                print(" ", shop["shop_name"])

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

            output_file = os.path.join("output", "gemstone_sellers_test.xlsx")

            # Prepare individual cabochon listings for Excel
            shop_names = {
                shop.get("shop_id"): shop.get("shop_name")
                for shop in final_shops
            }

            listing_rows = []

            for listing in cabochon_shop_listings:
                listing_rows.append({
                    "Shop Name": shop_names.get(listing.get("shop_id")),
                    "Listing Title": listing.get("title"),
                    "Listing ID": listing.get("listing_id"),
                    "WYSIWYG Status": listing.get("wysiwyg_status"),
                    "Listing URL": listing.get("url"),
                })

            listings_df = pd.DataFrame(listing_rows)

            # Save both worksheets in one Excel file
            with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Shops", index=False)
                listings_df.to_excel(
                    writer,
                    sheet_name="Cabochon Listings",
                    index=False
                )

            print("\nExcel file created:", output_file)
            print("Shops exported:", len(df))

        else:
            print("Search unsuccessful.")
            print("Response:", response.text[:500])

    except requests.RequestException as error:
        print("Search error:", error)

if __name__ == "__main__":
    main()