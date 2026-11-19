"""Local-only prototype; authentication required before public deployment."""
from flask import Flask, render_template, request, abort, redirect, url_for
from favourite_feed.database import connect_database, setup_database
from favourite_feed.filters import is_visible

app = Flask(__name__)


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
