"""Gemstone feed, settings, listing actions and dashboard routes."""
from datetime import datetime, timezone
import json
from flask import render_template, request, abort, redirect, url_for, jsonify
from favourite_feed.database import connect_database
from favourite_feed.filters import is_visible, DEFAULT_EXCLUSIONS, DEFAULT_PREFERENCES
from favourite_feed.currency import price_context
from favourite_feed import refresh_jobs

# Read saved filtering preferences or supply defaults for a new installation.
def preferences(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS feed_settings (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
    row = conn.execute("SELECT value FROM feed_settings WHERE id=1").fetchone()
    if row:
        settings = json.loads(row[0])
        # Upgrade previously saved settings once, preserving user-added exclusions.
        # The marker lets users subsequently remove any default term permanently.
        if not settings.get("finished_jewellery_defaults_v1"):
            settings["exclusions"] = list(dict.fromkeys(
                settings.get("exclusions", []) + list(DEFAULT_EXCLUSIONS)
            ))
            settings["finished_jewellery_defaults_v1"] = True
            conn.execute("UPDATE feed_settings SET value=? WHERE id=1", (json.dumps(settings),))
        return settings
    return dict(exclusions=list(DEFAULT_EXCLUSIONS), preferences=list(DEFAULT_PREFERENCES), preferred_only=False, show_excluded=False, finished_jewellery_defaults_v1=True)

# GET displays the settings form; POST saves the submitted filters and returns to the feed.
def settings():
    with connect_database() as conn:
        current = preferences(conn)
        if request.method == "POST":
            current = {key: list(dict.fromkeys(v.strip() for v in request.form.get(key, "").splitlines() if v.strip())) for key in ("exclusions", "preferences")}
            current.update(preferred_only="preferred_only" in request.form, show_excluded="show_excluded" in request.form, finished_jewellery_defaults_v1=True)
            conn.execute("INSERT OR REPLACE INTO feed_settings VALUES (1, ?)", (json.dumps(current),))
            return redirect(url_for("index"))
    return render_template("settings.html", settings=current)

# Create the undo history table if needed, storing each listing's previous state.
def ensure_history(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS feed_actions (
        action_id INTEGER PRIMARY KEY, listing_id INTEGER NOT NULL,
        old_seen TEXT, old_liked INTEGER NOT NULL)""")


# Handle a single seen/favourite action, validating the request and recording the old state first.
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
    # Swipe mode expects a small JSON response instead of a full page redirect.
    if request.headers.get("X-Feed-Action") == "swipe":
        with connect_database() as conn:
            saved = conn.execute("SELECT liked, seen_at FROM listings WHERE listing_id=?", (listing_id,)).fetchone()
        return jsonify(listing_id=listing_id, liked=bool(saved["liked"]), seen=bool(saved["seen_at"]))
    page = request.form.get("page", "1")
    try:
        page = max(1, int(page))
    except ValueError:
        page = 1
    return redirect(url_for("index", mode=request.form.get("mode", "unseen"), view="swipe" if request.form.get("view") == "swipe" else "grid", page=page))


def mark_page_seen():
    """Dismiss exactly the displayed unseen IDs; never alter favourites."""
    raw_ids = request.form.getlist("listing_id")
    if not 1 <= len(raw_ids) <= 10:
        abort(400)
    try:
        ids = [int(value) for value in raw_ids]
    except ValueError:
        abort(400)
    if any(value <= 0 for value in ids) or len(set(ids)) != len(ids):
        abort(400)
    with connect_database() as conn:
        ensure_history(conn)
        conn.execute("BEGIN IMMEDIATE")
        now = datetime.now(timezone.utc).isoformat()
        for listing_id in ids:
            row = conn.execute("SELECT seen_at, liked FROM listings WHERE listing_id=?", (listing_id,)).fetchone()
            if row is None:
                abort(400)
            if row["seen_at"]:
                continue
            conn.execute("INSERT INTO feed_actions(listing_id, old_seen, old_liked) VALUES (?, ?, ?)",
                         (listing_id, row["seen_at"], row["liked"]))
            conn.execute("UPDATE listings SET seen_at=? WHERE listing_id=?", (now, listing_id))
    return redirect(url_for("index", mode="unseen", page=1), code=303)


# Restore the most recent recorded listing state and remove that entry from undo history.
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


# Make the currency formatting helper available to all page templates.
def currency_context():
    return {"price_display": price_context()}

def feed_breakdown(rows, filters, refresh_status):
    """Disjoint inventory counts, plus counts for the latest tracked refresh."""
    def visible(row):
        return is_visible(row["title"],
                          exclusions=filters["exclusions"],
                          preferences=filters["preferences"],
                          preferred_only=filters["preferred_only"],
                          show_excluded=filters["show_excluded"])

    # Count each listing in exactly one of three groups: seen, filtered or visible unseen.
    def tally(items):
        counts = {"collected": len(items), "unseen": 0, "filtered": 0, "seen": 0}
        for row in items:
            if row["seen_at"]:
                counts["seen"] += 1
            elif not visible(row):
                counts["filtered"] += 1
            else:
                counts["unseen"] += 1
        return counts

    overall = tally(rows)
    run = None
    if refresh_status.get("started_at"):
        start = refresh_status["started_at"]
        end = refresh_status.get("finished_at")
        run_rows = [row for row in rows if row["discovered_at"] >= start
                    and (not end or row["discovered_at"] <= end)]
        run = tally(run_rows)
    return {"overall": overall, "run": run}


def dashboard():
    """App launcher; existing / remains the gemstone feed."""
    with connect_database() as conn:
        filters = preferences(conn)
        rows = conn.execute("SELECT title, seen_at, discovered_at FROM listings").fetchall()
        active_shops = conn.execute(
            "SELECT COUNT(*) FROM monitored_shops WHERE is_active=1"
        ).fetchone()[0]
        liked = conn.execute("SELECT COUNT(*) FROM listings WHERE liked=1").fetchone()[0]
    counts = feed_breakdown(rows, filters, refresh_jobs.snapshot())["overall"]
    return render_template("dashboard.html", counts=counts,
                           active_shops=active_shops, liked=liked,
                           refresh_status=refresh_jobs.snapshot())


# Build the main feed from saved listings, applying filters, display mode and pagination.
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
    # Calculate totals before filtering so the page can explain where all collected listings went.
    breakdown = feed_breakdown(rows, filters, refresh_jobs.snapshot())
    listings = [r for r in rows if
                (mode == "liked" and r["liked"]) or
                (mode == "seen" and r["seen_at"]) or
                (mode == "unseen" and not r["seen_at"] and is_visible(r["title"], exclusions=filters["exclusions"], preferences=filters["preferences"], preferred_only=filters["preferred_only"], show_excluded=filters["show_excluded"]))]
    # Show recently marked favourites first; unseen swipe mode instead displays one listing at a time.
    if mode == "liked":
        listings.sort(key=lambda row: (row["seen_at"] or "", row["listing_id"]), reverse=True)
    if mode == "unseen" and request.args.get("view") == "swipe":
        return render_template("swipe.html", item=listings[0] if listings else None, count=len(listings), refresh_status=refresh_jobs.snapshot(), breakdown=breakdown)
    # Divide the filtered list into pages of ten and keep the requested page within bounds.
    total_listings = len(listings)
    page_size = 10
    total_pages = max(1, (total_listings + page_size - 1) // page_size)
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1
    page = min(max(1, page), total_pages)
    listings = listings[(page - 1) * page_size:page * page_size]
    return render_template("feed.html", listings=listings, mode=mode,
                           total_listings=total_listings, page=page, total_pages=total_pages,
                           refresh_status=refresh_jobs.snapshot(), breakdown=breakdown)


# Mark a listing as seen before redirecting to its stored Etsy address.
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

# Load the selected listing, its seller name and all saved photos for the detail page.
def detail(listing_id):
    with connect_database() as conn:
        listing = conn.execute("SELECT l.*, s.shop_name FROM listings l JOIN monitored_shops s USING(shop_id) WHERE listing_id=?", (listing_id,)).fetchone()
        images = conn.execute("SELECT image_url FROM listing_images WHERE listing_id=? ORDER BY image_rank", (listing_id,)).fetchall()
    if listing is None:
        abort(404)
    return render_template("detail.html", listing=listing, images=images)



# Associate URL paths and HTTP methods with the functions above. GET reads pages; POST submits actions.
def register_feed_routes(app):
    app.route("/settings", methods=["GET", "POST"])(settings)
    app.post("/action/<int:listing_id>")(action)
    app.post("/mark-page-seen")(mark_page_seen)
    app.post("/undo")(undo)
    app.context_processor(currency_context)
    app.get("/dashboard")(dashboard)
    app.get("/")(index)
    app.post("/etsy/<int:listing_id>")(etsy)
    app.get("/listing/<int:listing_id>")(detail)
