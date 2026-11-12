import sqlite3

connection = sqlite3.connect("gemstone_sellers.db")

cursor = connection.cursor()

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

connection.commit()
connection.close()

print("Database created successfully.")