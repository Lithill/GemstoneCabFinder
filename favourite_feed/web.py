"""Local-only prototype; authentication required before public deployment."""
from datetime import datetime, timezone
from flask import Flask, render_template, request, abort, redirect, url_for
from favourite_feed.database import connect_database, setup_database
from favourite_feed.filters import is_visible

app = Flask(__name__)


def ensure_history(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS feed_actions (
        action_id INTEGER PRIMARY KEY, listing_id INTEGER NOT NULL,
        old_seen TEXT, old_liked INTEGER NOT NULL)""")


@app.post("/action/<int:listing_id>")
def action(listing_id):
    operation = request.form.get("operation")
    if operation not in ("seen", "like"):
        abort(400)
    with connect_database() as conn:
        ensure_history(conn)
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT seen_at, liked FROM listings WHERE listing_id=?", (listing_id,)).fetchone()
        if row is None:
            abort(404)
        conn.execute("INSERT INTO feed_actions(listing_id, old_seen, old_liked) VALUES (?, ?, ?)",
                     (listing_id, row["seen_at"], row["liked"]))
        conn.execute("UPDATE listings SET seen_at=?, liked=? WHERE listing_id=?",
                     (datetime.now(timezone.utc).isoformat(), int(operation == "like" or row["liked"]), listing_id))
    return redirect(url_for("index"))


@app.post("/undo")
def undo():
    with connect_database() as conn:
        ensure_history(conn)
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM feed_actions ORDER BY action_id DESC LIMIT 1").fetchone()
        if row:
            conn.execute("UPDATE listings SET seen_at=?, liked=? WHERE listing_id=?",
                         (row["old_seen"], row["old_liked"], row["listing_id"]))
            conn.execute("DELETE FROM feed_actions WHERE action_id=?", (row["action_id"],))
    return redirect(url_for("index"))


@app.get("/")
def index():
    mode = request.args.get("mode", "unseen")
    with connect_database() as conn:
        rows = conn.execute("""
            SELECT l.*, s.shop_name,
                (SELECT image_url FROM listing_images i
                 WHERE i.listing_id=l.listing_id ORDER BY image_rank LIMIT 1) AS photo
            FROM listings l JOIN monitored_shops s USING(shop_id)
            ORDER BY published_at DESC, listing_id DESC
        """).fetchall()
    listings = [r for r in rows if
                (mode == "liked" and r["liked"]) or
                (mode == "unseen" and not r["seen_at"] and is_visible(r["title"]))]
    return render_template("feed.html", listings=listings, mode=mode)


@app.get("/listing/<int:listing_id>")
def detail(listing_id):
    with connect_database() as conn:
        listing = conn.execute("SELECT l.*, s.shop_name FROM listings l JOIN monitored_shops s USING(shop_id) WHERE listing_id=?", (listing_id,)).fetchone()
        images = conn.execute("SELECT image_url FROM listing_images WHERE listing_id=? ORDER BY image_rank", (listing_id,)).fetchall()
    if listing is None:
        abort(404)
    return render_template("detail.html", listing=listing, images=images)


if __name__ == "__main__":
    setup_database()
    app.run(host="127.0.0.1", port=5000, debug=False)
