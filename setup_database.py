import sqlite3

# Open the original seller database, not the dashboard database.
connection = sqlite3.connect("data/gemstone_sellers.db")

cursor = connection.cursor()

# Create the legacy shops table if absent, preserving existing records.
cursor.execute("""
    CREATE TABLE IF NOT EXISTS shops (
        shop_id INTEGER PRIMARY KEY,
        shop_name TEXT,
        rating REAL,
        review_count INTEGER,
        shop_age_days INTEGER,
        shipping_country TEXT,
        last_checked TEXT
    )
""")

# Commit the schema operation and close the connection.
connection.commit()
connection.close()

print("Database created successfully.")