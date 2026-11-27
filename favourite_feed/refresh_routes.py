"""Refresh endpoints; share the application refresh lock with seller management."""
from flask import jsonify, render_template, request, abort
from favourite_feed import database, refresh_jobs
from favourite_feed.database import connect_database
from favourite_feed.currency import update_rates
from favourite_feed.refresh import refresh_shop


# Connect browser refresh requests to the Python functions that perform the work.
def register_refresh_routes(app, refresh_lock):
    # Update cached exchange rates when requested.
    @app.post("/refresh/rates")
    def refresh_rates():
        return jsonify(updated=update_rates())

    # Return saved progress as JSON (structured data the browser can read).
    @app.get("/refresh/status")
    def refresh_status():
        return jsonify(refresh_jobs.snapshot())

    # Start or resume a saved refresh run.
    @app.post("/refresh/start")
    def refresh_start():
        return jsonify(refresh_jobs.start())

    # Pause the saved run.
    @app.post("/refresh/pause")
    def refresh_pause():
        return jsonify(refresh_jobs.pause())

    # Process one queued shop through the resumable refresh system.
    @app.post("/refresh/step")
    def refresh_step():
        return jsonify(refresh_jobs.step())

    # Display the refresh interface, indicating whether the demo database is in use.
    @app.get("/refresh")
    def refresh_page():
        return render_template("refresh.html", demo=database.DB_PATH.name == "favourite_feed_demo.db")



    # Return active sellers for the individual-shop refresh interface.
    @app.get("/refresh/shops")
    def refresh_shops():
        with connect_database() as conn:
            shops = conn.execute("SELECT shop_id, shop_name, last_checked FROM monitored_shops WHERE is_active=1 ORDER BY shop_id").fetchall()
        return jsonify([dict(row) for row in shops])

    # Accept at most five positive integer shop IDs and stop early on a rate limit.
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

    # Refresh one active seller using the shared in-process lock.
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
        # Always release the lock, even after an error.
        finally:
            refresh_lock.release()
