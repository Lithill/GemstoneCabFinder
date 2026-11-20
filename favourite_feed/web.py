"""Local-only prototype; authentication required before public deployment."""
from datetime import datetime, timezone
from flask import Flask, render_template, request, abort, redirect, url_for, jsonify
from favourite_feed.database import connect_database, setup_database
from favourite_feed.filters import is_visible, DEFAULT_EXCLUSIONS, DEFAULT_PREFERENCES
import json
from threading import Lock
from favourite_feed.currency import price_context, update_rates
from favourite_feed.refresh import refresh_shop
from favourite_feed import database, refresh_jobs

app = Flask(__name__)
refresh_lock = Lock()

# Explicit opt-in only. The live site keeps its non-saving public prototype
# until private login is configured and a separate deployment is approved.
# The isolated module imports cryptography; do not load it on existing installs.
import os
if os.environ.get("HEALTH_TRACKER_PREVIEW_ENABLED") == "1":
    # Register the same audited login blueprint and protected preview view
    # without introducing any health-data write endpoint.
    from favourite_feed.health_auth import health_auth, require_health_login
    app.register_blueprint(health_auth)

    @app.get("/private-symptom-tracker")
    @require_health_login
    def private_symptom_tracker():
        response = app.make_response(render_template("symptom_tracker.html"))
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

@app.after_request
def prevent_stale_feed(response):
    response.headers["Cache-Control"] = "no-store"
    return response


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

@app.route("/settings", methods=["GET", "POST"])
def settings():
    with connect_database() as conn:
        current = preferences(conn)
        if request.method == "POST":
            current = {key: list(dict.fromkeys(v.strip() for v in request.form.get(key, "").splitlines() if v.strip())) for key in ("exclusions", "preferences")}
            current.update(preferred_only="preferred_only" in request.form, show_excluded="show_excluded" in request.form, finished_jewellery_defaults_v1=True)
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


@app.context_processor
def currency_context():
    return {"price_display": price_context()}

@app.post("/refresh/rates")
def refresh_rates():
    return jsonify(updated=update_rates())

@app.get("/refresh/status")
def refresh_status():
    return jsonify(refresh_jobs.snapshot())

@app.post("/refresh/start")
def refresh_start():
    return jsonify(refresh_jobs.start())

@app.post("/refresh/pause")
def refresh_pause():
    return jsonify(refresh_jobs.pause())

@app.post("/refresh/step")
def refresh_step():
    return jsonify(refresh_jobs.step())

@app.get("/refresh")
def refresh_page():
    return render_template("refresh.html", demo=database.DB_PATH.name == "favourite_feed_demo.db")

@app.get("/refresh/shops")
def refresh_shops():
    with connect_database() as conn:
        shops = conn.execute("SELECT shop_id, shop_name, last_checked FROM monitored_shops WHERE is_active=1 ORDER BY shop_id").fetchall()
    return jsonify([dict(row) for row in shops])

@app.post("/refresh/batch")
def refresh_batch():
    ids = request.get_json(silent=True)
    if not isinstance(ids, list) or not 1 <= len(ids) <= 5 or any(type(i) is not int or i <= 0 for i in ids):
        abort(400)
    results = []
    for shop_id in ids:
        response = refresh_one(shop_id)
        if isinstance(response, tuple):
            return response
        result = response.get_json()
        results.append(result)
        if result.get("error") and "rate limit" in result["error"].lower():
            break
    return jsonify(results)

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

def feed_breakdown(rows, filters, refresh_status):
    """Disjoint inventory counts, plus counts for the latest tracked refresh."""
    def visible(row):
        return is_visible(row["title"],
                          exclusions=filters["exclusions"],
                          preferences=filters["preferences"],
                          preferred_only=filters["preferred_only"],
                          show_excluded=filters["show_excluded"])

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


@app.get("/symptom-tracker")
def symptom_tracker():
    """Read-only prototype: no health data is accepted or stored."""
    response = app.make_response(render_template("symptom_tracker.html"))
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'"
    return response


@app.get("/dashboard")
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
    breakdown = feed_breakdown(rows, filters, refresh_jobs.snapshot())
    listings = [r for r in rows if
                (mode == "liked" and r["liked"]) or
                (mode == "seen" and r["seen_at"]) or
                (mode == "unseen" and not r["seen_at"] and is_visible(r["title"], exclusions=filters["exclusions"], preferences=filters["preferences"], preferred_only=filters["preferred_only"], show_excluded=filters["show_excluded"]))]
    if mode == "liked":
        listings.sort(key=lambda row: (row["seen_at"] or "", row["listing_id"]), reverse=True)
    if mode == "unseen" and request.args.get("view") == "swipe":
        return render_template("swipe.html", item=listings[0] if listings else None, count=len(listings), refresh_status=refresh_jobs.snapshot(), breakdown=breakdown)
    return render_template("feed.html", listings=listings, mode=mode, refresh_status=refresh_jobs.snapshot(), breakdown=breakdown)


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
