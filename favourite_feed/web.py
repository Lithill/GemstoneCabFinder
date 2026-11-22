"""Local-only prototype; authentication required before public deployment."""
from datetime import datetime, timezone
from flask import Flask, render_template, request, abort, redirect, url_for, jsonify
from favourite_feed.database import connect_database, setup_database
from favourite_feed.filters import is_visible, DEFAULT_EXCLUSIONS, DEFAULT_PREFERENCES
import json
from threading import Lock
import hashlib
import secrets
from favourite_feed.currency import price_context, update_rates
from favourite_feed.refresh import refresh_shop
from favourite_feed import database, refresh_jobs
from favourite_feed.gemstone_quiz import identify as identify_quiz_gem, options as quiz_options

app = Flask(__name__)
refresh_lock = Lock()

# Opt-in private preview only; disabled on the live installation by default.
# This module and its cryptography dependency are not loaded unless enabled.
import os
if os.environ.get("HEALTH_TRACKER_PREVIEW_ENABLED") == "1":
    from favourite_feed.health_staging import register_private_preview
    register_private_preview(app)


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
    page = request.form.get("page", "1")
    try:
        page = max(1, int(page))
    except ValueError:
        page = 1
    return redirect(url_for("index", mode=request.form.get("mode", "unseen"), view="swipe" if request.form.get("view") == "swipe" else "grid", page=page))


@app.post("/mark-page-seen")
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

@app.get("/gemstone-quiz")
def gemstone_quiz():
    """Photo-first, read-only identification practice using collected Etsy images."""
    try:
        position = max(0, int(request.args.get("position", "0")))
    except (TypeError, ValueError):
        position = 0
    seed = request.args.get("seed", "")
    if not (len(seed) == 16 and all(c in "0123456789abcdef" for c in seed)):
        seed = secrets.token_hex(8)
    with connect_database() as conn:
        rows = conn.execute("""
            SELECT l.listing_id, l.title, l.listing_url,
                   (SELECT image_url FROM listing_images i
                    WHERE i.listing_id = l.listing_id
                    ORDER BY image_rank LIMIT 1) AS photo
            FROM listings l
            WHERE EXISTS (SELECT 1 FROM listing_images i
                          WHERE i.listing_id = l.listing_id
                            AND i.image_url IS NOT NULL AND i.image_url != '')
            ORDER BY l.published_at DESC, l.listing_id DESC
        """).fetchall()
    # Only quiz titles with one recognised gemstone; do not guess from photos.
    eligible = [(row, identify_quiz_gem(row["title"])) for row in rows]
    rows = [(row, gem) for row, gem in eligible if gem]
    # A fresh random order per quiz, stable while navigating Previous/Next.
    rows.sort(key=lambda row: hashlib.sha256(
        f"{seed}:{row[0]['listing_id']}".encode("ascii")).digest())
    total = len(rows)
    position = min(position, max(0, total - 1))
    item, answer = rows[position] if total else (None, None)
    return render_template("gemstone_quiz.html",
                           item=item, answer=answer,
                           choices=quiz_options(answer, seed, item["listing_id"]) if item else [],
                           position=position, total=total, seed=seed)


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
