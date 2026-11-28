"""Local confirmations only; never claim to read or write Etsy favourites."""
from favourite_feed.database import connect_database


def setup(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS etsy_favourite_confirmations (shop_id INTEGER PRIMARY KEY)")


def set_confirmed(sid, confirmed):
    # Only monitored shops can be marked, and undo never affects monitoring.
    with connect_database() as conn:
        setup(conn)
        if not conn.execute("SELECT 1 FROM monitored_shops WHERE shop_id=?", (sid,)).fetchone():
            raise ValueError("Unknown shop.")
        if confirmed:
            conn.execute("INSERT OR IGNORE INTO etsy_favourite_confirmations(shop_id) VALUES (?)", (sid,))
        else:
            conn.execute("DELETE FROM etsy_favourite_confirmations WHERE shop_id=?", (sid,))
