"""Local-only prototype; authentication required before public deployment."""
from datetime import datetime, timezone
from flask import Flask, render_template, request, abort, redirect, url_for, jsonify
from favourite_feed.database import connect_database, setup_database
from favourite_feed.filters import is_visible, DEFAULT_EXCLUSIONS, DEFAULT_PREFERENCES
import json
from threading import Lock
from favourite_feed.refresh import refresh_shop
from favourite_feed import database

app = Flask(__name__)
refresh_lock = Lock()

@app.after_request
def prevent_stale_feed(response):
    response.headers["Cache-Control"] = "no-store"
    return response


def preferences(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS feed_settings (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
    row = conn.execute("SELECT value FROM feed_settings WHERE id=1").fetchone()
    return json.loads(row[0]) if row else dict(exclusions=list(DEFAULT_EXCLUSIONS), preferences=list(DEFAULT_PREFERENCES), preferred_only=False, show_excluded=False)

@app.route("/settings", methods=["GET", "POST"])
def settings():
    with connect_database() as conn:
        current = preferences(conn)
        if request.method == "POST":
            current = {key: list(dict.fromkeys(v.strip() for v in request.form.get(key, "").splitlines() if v.strip())) for key in ("exclusions", "preferences")}
            current.update(preferred_only="preferred_only" in request.form, show_excluded="show_excluded" in request.form)
            conn.execute("INSERT OR REPLACE INTO feed_settings VALUES (1, ?)", (json.dumps(current),))
            return redirect(url_for("index"))
    return render_template("settings.html", settings=current)

def ensure_history(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS feed_actions (
        action_id INTEGER PRIMARY KEY, listing_id INTEGER NOT NULL,
        old_seen TEXT, old_liked INTEGER NOT NULL)""")


@app.post("/action/<int:listing_id>")
def action(listing_id):
    operation = request.form.get("operation")
    if operation not in ("seen", "like", "unseen", "unlike"):
        abort(400)
    with connect_database() as conn:
        ensure_history(conn)
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT seen_at, liked FROM listings WHERE listing_id=?", (listing_id,)).fetchone()
        if row is None:
            abort(404)
        conn.execute("INSERT INTO feed_actions(listing_id, old_seen, old_liked) VALUES (?, ?, ?)",
                     (listing_id, row["seen_at"], row["liked"]))
        seen = None if operation == "unseen" else (datetime.now(timezone.utc).isoformat() if operation in ("seen", "like") else row["seen_at"])
        liked = 0 if operation == "unlike" else int(operation == "like" or row["liked"])
        conn.execute("UPDATE listings SET seen_at=?, liked=? WHERE listing_id=?", (seen, liked, listing_id))
    print(f"Feed action: {listing_id} operation={operation}", flush=True)
    if request.headers.get("X-Feed-Action") == "swipe":
        with connect_database() as conn:
            saved = conn.execute("SELECT liked, seen_at FROM listings WHERE listing_id=?", (listing_id,)).fetchone()
        return jsonify(listing_id=listing_id, liked=bool(saved["liked"]), seen=bool(saved["seen_at"]))
    return redirect(url_for("index", mode=request.form.get("mode", "unseen"), view="swipe" if request.form.get("view") == "swipe" else "grid"))


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
    return redirect(url_for("index", mode=request.form.get("mode", "unseen"), view="swipe" if request.form.get("view") == "swipe" else "grid"))


@app.get("/refresh")
def refresh_page():
    return render_template("refresh.html", demo=database.DB_PATH.name == "favourite_feed_demo.db")

@app.get("/refresh/shops")
def refresh_shops():
    with connect_database() as conn:
        shops = conn.execute("SELECT shop_id, shop_name, last_checked FROM monitored_shops WHERE is_active=1 ORDER BY shop_id").fetchall()
    return jsonify([dict(row) for row in shops])

@app.post("/refresh/shop/<int:shop_id>")
def refresh_one(shop_id):
    if not refresh_lock.acquire(blocking=False):
        return jsonify(error="Another shop is being refreshed. Try again."), 409
    try:
        with connect_database() as conn:
            shop = conn.execute("SELECT * FROM monitored_shops WHERE shop_id=? AND is_active=1", (shop_id,)).fetchone()
            before = conn.execute("SELECT COUNT(*) FROM listings WHERE shop_id=?", (shop_id,)).fetchone()[0]
        if shop is None:
            abort(404)
        error = None
        try:
            message = refresh_shop(shop)
        except Exception as exc:
            error = str(exc)
            message = "Failed"
        with connect_database() as conn:
            after = conn.execute("SELECT COUNT(*) FROM listings WHERE shop_id=?", (shop_id,)).fetchone()[0]
        return jsonify(message=message, new=after-before, error=error, baseline=not shop["last_checked"] and not error)
    finally:
        refresh_lock.release()

@app.get("/")
def index():
    mode = request.args.get("mode", "unseen")
    with connect_database() as conn:
        filters = preferences(conn)
        rows = conn.execute("""
            SELECT l.*, s.shop_name,
                (SELECT image_url FROM listing_images i
                 WHERE i.listing_id=l.listing_id ORDER BY image_rank LIMIT 1) AS photo
            FROM listings l JOIN monitored_shops s USING(shop_id)
            ORDER BY published_at DESC, listing_id DESC
        """).fetchall()
    listings = [r for r in rows if
                (mode == "liked" and r["liked"]) or
                (mode == "seen" and r["seen_at"]) or
                (mode == "unseen" and not r["seen_at"] and is_visible(r["title"], **filters))]
    if mode == "liked":
        listings.sort(key=lambda row: (row["seen_at"] or "", row["listing_id"]), reverse=True)
    if mode == "unseen" and request.args.get("view") == "swipe":
        return render_template("swipe.html", item=listings[0] if listings else None, count=len(listings))
    return render_template("feed.html", listings=listings, mode=mode)


@app.post("/etsy/<int:listing_id>")
def etsy(listing_id):
    with connect_database() as conn:
        ensure_history(conn)
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM listings WHERE listing_id=?", (listing_id,)).fetchone()
        if not row or not (row["listing_url"] or "").startswith("https://www.etsy.com/"):
            abort(404)
        if not row["seen_at"]:
            conn.execute("INSERT INTO feed_actions(listing_id,old_seen,old_liked) VALUES (?,?,?)", (listing_id,row["seen_at"],row["liked"]))
            conn.execute("UPDATE listings SET seen_at=? WHERE listing_id=?", (datetime.now(timezone.utc).isoformat(),listing_id))
    return redirect(row["listing_url"], code=303)

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
