
import sqlite3
from pathlib import Path

import pandas as pd

database_file = "data/gemstone_sellers.db"
excel_file = Path("output/gemstone_sellers_test.xlsx")
history_file = Path("data/reviewed_shop_ids.txt")

columns = [
    "Shop Name",
    "Shop ID",
    "Ships From",
    "Rating",
    "Reviews",
    "Shop URL",
]

# Load existing review history
reviewed_ids = set()

if history_file.exists():
    reviewed_ids = {
        line.strip()
        for line in history_file.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    }

# Load existing Excel worksheets
sheets = pd.read_excel(
    excel_file,
    sheet_name=None,
    dtype={"Shop ID": str},
)

shops_df = sheets.get(
    "Shops",
    pd.DataFrame(columns=columns),
).reindex(columns=columns)

existing_ids = set(
    shops_df["Shop ID"].dropna().astype(str).str.strip()
)

# Read previously saved shops from SQLite
with sqlite3.connect(database_file) as connection:
    saved_shops = connection.execute("""
        SELECT shop_id, shop_name, shipping_country,
               rating, review_count
        FROM shops
    """).fetchall()

    favourite_names = {
        row[0].casefold()
        for row in connection.execute(
            "SELECT shop_name FROM favourite_shops"
        )
        if row[0]
    }

# Also honour the manual exclusion file
excluded_names = set()

exclusion_file = Path("data/favourited_shops.txt")

if exclusion_file.exists():
    excluded_names = {
        line.strip().casefold()
        for line in exclusion_file.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip() and not line.strip().startswith("#")
    }

new_rows = []

for shop_id, shop_name, country, rating, reviews in saved_shops:
    shop_id_text = str(shop_id)

    if shop_id_text in reviewed_ids:
        continue

    if shop_id_text in existing_ids:
        continue

    if not shop_name:
        continue

    if shop_name.casefold() in favourite_names | excluded_names:
        continue

    new_rows.append({
        "Shop Name": shop_name,
        "Shop ID": shop_id_text,
        "Ships From": country,
        "Rating": rating,
        "Reviews": reviews,
        "Shop URL": f"https://www.etsy.com/shop/{shop_name}",
    })

    reviewed_ids.add(shop_id_text)

# Add older shops to the review list
new_df = pd.DataFrame(new_rows, columns=columns)

shops_df = pd.concat(
    [shops_df, new_df],
    ignore_index=True,
)

sheets["Shops"] = shops_df

# Save all existing worksheets, including shipping checks
with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
    for sheet_name, sheet_df in sheets.items():
        sheet_df.to_excel(
            writer,
            sheet_name=sheet_name,
            index=False,
        )

# Record every shop currently in the review list
reviewed_ids.update(existing_ids)

history_file.write_text(
    "".join(
        shop_id + "\n"
        for shop_id in sorted(reviewed_ids)
    ),
    encoding="utf-8",
)

print("Older shops added:", len(new_rows))
print("Total shops in review list:", len(shops_df))
print("Review history IDs:", len(reviewed_ids))
