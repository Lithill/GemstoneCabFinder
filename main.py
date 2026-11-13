# Gemstone cabochon seller search settings
import sqlite3
from datetime import datetime, timezone
import os
import re
import requests
import time
import pandas as pd
from openpyxl.styles import Font
from dotenv import load_dotenv
from config import (
    GEMSTONES,
    SEARCH_TERMS,
    TARGET_COUNTRIES,
    FINISHED_JEWELLERY_TERMS,
    WYSIWYG_POSITIVE_PHRASES,
    WYSIWYG_NEGATIVE_PHRASES,
    MIN_SHOP_AGE_DAYS,
    MIN_SHOP_RATING,
    MIN_SHOP_REVIEWS,
    MAX_LISTINGS_TO_SEARCH,
    MAX_SHOP_LISTINGS_TO_SEARCH,
    TARGET_SHIPPING_COUNTRIES,
)

# Load shops that should be excluded from search results
def load_favourited_shops(filename="data/favourited_shops.txt"):
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

def load_favourite_shops():
    """Load favourite Etsy shop names from the database."""
    with sqlite3.connect("data/gemstone_sellers.db") as connection:
        rows = connection.execute(
            "SELECT shop_name FROM favourite_shops"
        ).fetchall()

    return {row[0].casefold() for row in rows}

def classify_wysiwyg(title, description="", rare_find=False):
    """Classify evidence that the buyer receives the pictured stone."""
    text = (str(title) + " " + str(description)).casefold()

    for phrase in WYSIWYG_NEGATIVE_PHRASES:
        if phrase in text:
            return "Likely random selection"

    for phrase in WYSIWYG_POSITIVE_PHRASES:
        if phrase in text:
            return "Likely WYSIWYG"

    if rare_find:
        return "Possible WYSIWYG - Rare find"

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

def make_urls_clickable(worksheet):
    """Make Etsy URLs clickable in an Excel worksheet."""

    url_columns = ["Shop URL", "Evidence Listing URL"]

    for column in worksheet.iter_cols():
        header = column[0].value

        if header not in url_columns:
            continue

        for cell in column[1:]:
            url = cell.value

            if isinstance(url, str) and url.startswith("https://"):
                cell.hyperlink = url
                cell.font = Font(
                    color="0563C1",
                    underline="single",
                )

def update_review_list(new_shops, unknown_shipping_shops, output_file):
    """Add newly qualified shops without restoring manually deleted shops."""

    history_file = "data/reviewed_shop_ids.txt"

    columns = [
        "Shop Name",
        "Shop ID",
        "Ships From",
        "Rating",
        "Reviews",
        "Review Priority",
        "WYSIWYG Evidence",
        "Evidence Listing URL",
        "UK Delivery",
        "UK Postage GBP",
        "Shop URL",
    ]

    # Load IDs of shops previously placed on the review list
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as file:
            reviewed_ids = {
                line.strip()
                for line in file
                if line.strip()
            }
    else:
        reviewed_ids = set()

    # Load the existing Excel review list
    if os.path.exists(output_file):
        existing_df = pd.read_excel(
            output_file,
            sheet_name="Shops",
            dtype={"Shop ID": str}
        )
    else:
        existing_df = pd.DataFrame(columns=columns)

    existing_df = existing_df.reindex(columns=columns)

    # Remove favourite and manually excluded shops already in Excel
    excluded_names = load_favourited_shops()
    excluded_names.update(load_favourite_shops())

    existing_df = existing_df[
        ~existing_df["Shop Name"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.casefold()
        .isin(excluded_names)
    ].copy()

    existing_ids = {
        str(shop_id).strip()
        for shop_id in existing_df["Shop ID"].dropna()
    }

    # Record all shops already present, including older entries
    reviewed_ids.update(existing_ids)

    new_rows = []

    for shop in new_shops:
        shop_id = shop.get("shop_id")

        if shop_id is None:
            continue

        shop_id_text = str(shop_id)

        if shop_id_text in reviewed_ids:
            continue

        shop_name = shop.get("shop_name")

        if str(shop_name or "").strip().casefold() in excluded_names:
            continue

        new_rows.append({
            "Shop Name": shop_name,
            "Shop ID": shop_id,
            "Ships From": shop.get("shipping_from_country_iso"),
            "Rating": shop.get("review_average"),
            "Reviews": shop.get("review_count"),
            "Shop URL": f"https://www.etsy.com/shop/{shop_name}",
            "Review Priority": (
                "High"
                if shop.get("wysiwyg_status") == "Likely WYSIWYG"
                else "Medium"
                if shop.get("wysiwyg_status") == "Possible WYSIWYG - Rare find"
                else "Low"
                if shop.get("wysiwyg_status") == "Likely random selection"
                else "Normal"
            ),
            "WYSIWYG Evidence": shop.get(
                "wysiwyg_status", "Needs checking"
            ),
            "Evidence Listing URL": shop.get(
                "evidence_listing_url", ""
            ),
            "UK Delivery": "Needs checking",
            "UK Postage GBP": None,
        })

        reviewed_ids.add(shop_id_text)

    # Append only genuinely new shops
    new_df = pd.DataFrame(new_rows, columns=columns)

    updated_df = pd.concat(
        [existing_df, new_df],
        ignore_index=True
    )

    # Preserve the separate shipping-check worksheet
    if os.path.exists(output_file):
        try:
            unknown_df = pd.read_excel(
                output_file,
                sheet_name="Needs Shipping Check",
                dtype={"Shop ID": str}
            )
        except ValueError:
            unknown_df = pd.DataFrame()
    else:
        unknown_df = pd.DataFrame()

    unknown_columns = [
        "Shop Name",
        "Shop ID",
        "Rating",
        "Reviews",
        "Shipping Country",
        "Shop URL",
    ]

    unknown_df = unknown_df.reindex(columns=unknown_columns)

    known_unknown_ids = {
        str(shop_id).strip()
        for shop_id in unknown_df["Shop ID"].dropna()
    }

    unknown_rows = []

    for shop in unknown_shipping_shops:
        shop_id = shop.get("shop_id")

        if shop_id is None:
            continue

        if str(shop_id) in known_unknown_ids:
            continue

        shop_name = shop.get("shop_name")

        unknown_rows.append({
            "Shop Name": shop_name,
            "Shop ID": shop_id,
            "Rating": shop.get("review_average"),
            "Reviews": shop.get("review_count"),
            "Shipping Country": "Unknown",
            "Shop URL": f"https://www.etsy.com/shop/{shop_name}",
        })

        known_unknown_ids.add(str(shop_id))

    unknown_df = pd.concat(
        [
            unknown_df,
            pd.DataFrame(unknown_rows, columns=unknown_columns)
        ],
        ignore_index=True
    )

    # Save the updated review list
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        updated_df.to_excel(
            writer,
            sheet_name="Shops",
            index=False
        )

        unknown_df.to_excel(
            writer,
            sheet_name="Needs Shipping Check",
            index=False
        )

        make_urls_clickable(writer.sheets["Shops"])
        make_urls_clickable(writer.sheets["Needs Shipping Check"])

    # Save the history of shops already offered for review
    with open(history_file, "w", encoding="utf-8") as file:
        for shop_id in sorted(reviewed_ids):
            file.write(shop_id + "\n")

    print("New shops added to review list:", len(new_rows))
    print("Total shops remaining in review list:", len(updated_df))

def get_etsy_with_retries(url, headers, params=None):
    """Retry temporary Etsy timeouts and stop on rate limits."""

    for attempt in range(3):
        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=30,
            )

            if response.status_code == 429:
                print("Etsy API rate limit reached (HTTP 429).")
                raise RuntimeError("Etsy API rate limit reached")

            return response

        except (requests.Timeout, requests.ConnectionError) as error:
            print(f"  Request failed (attempt {attempt + 1}/3): {error}")

            if attempt < 2:
                time.sleep(5)

    print("  Etsy did not respond after 3 attempts.")
    return None

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

    favourited_shops = load_favourited_shops()
    favourite_shops = load_favourite_shops()

    favourited_shops.update(favourite_shops)

    print("Favourite shops loaded:", len(favourite_shops))
    print("Total excluded shops:", len(favourited_shops))

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
                "buyer_country": "GB",
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

            # Classify listings without printing every listing
            wysiwyg_counts = {
                "Likely WYSIWYG": 0,
                "Needs checking": 0,
                "Likely random selection": 0,
            }

            for listing in listings:
                title = listing.get("title") or ""
                description = listing.get("description") or ""

                wysiwyg_status = classify_wysiwyg(title, description)
                listing["wysiwyg_status"] = wysiwyg_status
                wysiwyg_counts[wysiwyg_status] += 1

            print("\nMarketplace listing classifications:")
            for status, count in wysiwyg_counts.items():
                print(f"  {status}: {count}")

            # Collect WYSIWYG evidence for each shop
            shop_wysiwyg_evidence = {}

            wysiwyg_priority = {
                "Likely WYSIWYG": 3,
                "Possible WYSIWYG - Rare find": 2,
                "Needs checking": 1,
                "Likely random selection": 0,
            }

            for listing in listings:
                shop_id = listing.get("shop_id")

                if shop_id is None:
                    continue

                status = listing.get("wysiwyg_status", "Needs checking")

                previous = shop_wysiwyg_evidence.get(shop_id)

                if previous is None or (
                    wysiwyg_priority[status]
                    > wysiwyg_priority[previous["status"]]
                ):
                    listing_id = listing.get("listing_id")

                    shop_wysiwyg_evidence[shop_id] = {
                        "status": status,
                        "listing_url": (
                            f"https://www.etsy.com/listing/{listing_id}"
                            if listing_id is not None
                            else ""
                        ),
                    }

            # Collect unique shops from the search results
            unique_shop_ids = set()

            for listing in listings:
                shop_id = listing.get("shop_id")

                if shop_id:
                    unique_shop_ids.add(shop_id)

            print("\nUnique shops found:", len(unique_shop_ids))

            # Check every unique shop
            qualifying_shops = []

            # Check only newly discovered shops not already saved
            shops_to_check = unique_shop_ids - set(saved_shops_by_id)

            print("New shops to check:", len(shops_to_check))
            print(
                "Previously saved shops skipped:",
                len(unique_shop_ids & set(saved_shops_by_id))
            )

            for shop_id in sorted(shops_to_check):

                shop_url = f"https://openapi.etsy.com/v3/application/shops/{shop_id}"

                shop_response = get_etsy_with_retries(
                    shop_url,
                    headers=headers,
                )

                if shop_response is None:
                    print("Skipping shop after repeated timeouts:", shop_id)
                    continue

                if shop_response.status_code != 200:
                    print(
                        "Could not retrieve shop:",
                        shop_id,
                        "HTTP status:",
                        shop_response.status_code,
                    )
                    continue

                shop = shop_response.json()

                shop_name = shop.get("shop_name")
                rating = shop.get("review_average")
                reviews = shop.get("review_count")

                # Exclude shops already listed in favourited_shops.txt
                if shop_name and shop_name.casefold() in favourited_shops:
                    print(f"\nSkipping excluded shop: {shop_name}")
                    continue

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

                if (
                    rating >= MIN_SHOP_RATING
                    and reviews >= MIN_SHOP_REVIEWS
                    and shop_age_days >= MIN_SHOP_AGE_DAYS
                ):
                    evidence = shop_wysiwyg_evidence.get(shop_id, {})

                    shop["wysiwyg_status"] = evidence.get(
                        "status", "Needs checking"
                    )
                    shop["evidence_listing_url"] = evidence.get(
                        "listing_url", ""
                    )

                    qualifying_shops.append(shop)

            print("\n" + "=" * 40)
            print("Shops passing rating, reviews and age checks:", len(qualifying_shops))

            # Filter shops by shipping-from country
            final_shops = []
            unknown_shipping_shops = []

            for shop in qualifying_shops:
                shipping_country = shop.get("shipping_from_country_iso")

                if shipping_country in TARGET_SHIPPING_COUNTRIES:
                    final_shops.append(shop)

                elif not shipping_country:
                    unknown_shipping_shops.append(shop)

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
            print("FINAL QUALIFYING SHOPS:", len(final_shops))
            print("Shops with unknown shipping country:",
                len(unknown_shipping_shops))

            for shop in final_shops:
                print("Qualified:", shop.get("shop_name"))

            # Update the permanent Excel shop review list
            output_file = r"G:\My Drive\GemstoneCabFinder\gemstone_sellers_test.xlsx"

            update_review_list(
                final_shops,
                unknown_shipping_shops,
                output_file
            )

            # Save newly qualified shops only after updating Excel
            for shop in final_shops:
                save_shop_to_database(shop)

            print("\nExcel review list updated:", output_file)
            print(
                "Shops needing shipping verification:",
                len(unknown_shipping_shops)
            )

        else:
            print("Search unsuccessful.")
            print("Response:", response.text[:500])

    except requests.RequestException as error:
        print("Search error:", error)

if __name__ == "__main__":
    main()