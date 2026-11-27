"""Seller management routes, registered with the shared refresh lock."""
import json
from werkzeug.exceptions import HTTPException
from flask import request, abort, jsonify, render_template
from favourite_feed.database import connect_database


# Register both seller pages using the lock shared with the refresh section.
def register_seller_routes(app, refresh_lock):
    @app.route("/discover", methods=["GET","POST"])
    # Display pending discoveries or process a submitted search or review action.
    def discover():
        from favourite_feed import discovery
        from urllib.parse import urlsplit
        message = ""
        if request.method == "POST":
            # Check that the submitted request came from the same website origin.
            source = urlsplit(request.headers.get("Origin") or request.headers.get("Referer") or "")
            expected = urlsplit(request.host_url)
            if (source.scheme,source.netloc)!=(expected.scheme,expected.netloc):
                abort(403)
            # Return a conflict immediately rather than waiting for another locked operation to finish.
            if not refresh_lock.acquire(blocking=False):
                return jsonify(error="Another operation is running."),409
            try:
                operation=request.form.get("operation")
                if operation=="settings":
                    terms=discovery.terms_from_text(request.form.get("terms",""))
                    with connect_database() as conn:
                        discovery.setup(conn)
                        conn.execute("UPDATE discovery_settings SET terms=? WHERE id=1",(json.dumps(terms),))
                    message="Search terms saved."
                elif operation=="start":
                    discovery.start()
                    message="Search started."
                # The browser requests one search step at a time and receives a JSON progress message.
                elif operation=="step":
                    return jsonify(message=discovery.step())
                elif operation in ("favourite","reject"):
                    discovery.review(int(request.form.get("shop_id","")),operation)
                    message="Shop added to favourites." if operation=="favourite" else "Shop rejected."
                else:
                    abort(400)
            except ValueError as exc:
                if request.form.get("operation")=="step":
                    return jsonify(error=str(exc)),400
                message=str(exc)
            except HTTPException:
                raise
            except Exception:
                app.logger.exception("Discovery operation failed")
                message="Operation failed. Search progress retained; try again later."
                if request.form.get("operation")=="step":
                    return jsonify(error=message),503
            # Release the lock even if the operation fails or returns early.
            finally:
                refresh_lock.release()
        with connect_database() as conn:
            discovery.setup(conn)
            terms=json.loads(conn.execute("SELECT terms FROM discovery_settings WHERE id=1").fetchone()[0])
            run=conn.execute("SELECT * FROM discovery_run WHERE id=1").fetchone()
            # Show only pending sellers not already monitored, with likely pictured-stone sellers first.
            pending=conn.execute("""SELECT * FROM discovery_shops d WHERE status='pending'
                AND NOT EXISTS (SELECT 1 FROM monitored_shops m WHERE m.shop_id=d.shop_id)
                ORDER BY CASE evidence WHEN 'Likely WYSIWYG' THEN 0 WHEN 'Likely random selection' THEN 2 ELSE 1 END, name""").fetchall()
            queued=conn.execute("SELECT COUNT(*) FROM discovery_queue").fetchone()[0]
        return render_template("discover.html",terms=terms,run=run,pending=pending,queued=queued,message=message)


    @app.route("/favourite-shops", methods=["GET", "POST"])
    # Display monitored sellers and handle adding, pausing, resuming or importing recent listings.
    def favourite_shops():
        from favourite_feed.shop_management import add_shop, import_recent
        from urllib.parse import urlsplit
        message = ""
        if request.method == "POST":
            # Check the request origin before allowing a change to saved sellers.
            origin = request.headers.get("Origin")
            referer = request.headers.get("Referer")
            expected = urlsplit(request.host_url)
            source = urlsplit(origin or referer or "")
            if (source.scheme, source.netloc) != (expected.scheme, expected.netloc):
                abort(403)
            if not refresh_lock.acquire(blocking=False):
                return "A refresh is in progress. Try again shortly.", 409
            try:
                operation = request.form.get("operation")
                if operation == "add":
                    sid, created = add_shop(request.form.get("shop",""))
                    message = "Shop added. Future listings will be monitored." if created else "Shop already exists; its monitoring status is unchanged."
                elif operation in ("pause","resume","import"):
                    sid = int(request.form.get("shop_id",""))
                    if operation == "import":
                        count = import_recent(sid,int(request.form.get("limit","0")))
                        message = f"Imported {count} additional listings."
                    # Pause or resume monitoring by changing the active flag, not deleting the shop or its listings.
                    else:
                        with connect_database() as conn:
                            conn.execute("UPDATE monitored_shops SET is_active=? WHERE shop_id=?", (int(operation=="resume"),sid))
                        message = "Monitoring resumed." if operation=="resume" else "Monitoring paused. Existing listings retained."
                else:
                    abort(400)
            except ValueError as exc:
                message = str(exc)
            except HTTPException:
                raise
            except Exception:
                app.logger.exception("Favourite shop operation failed")
                message = "Shop operation could not finish. Check the list below; partial imports can be retried."
            finally:
                refresh_lock.release()
        with connect_database() as conn:
            # Count saved listings for each seller and show active sellers before paused ones.
            shops = conn.execute("""SELECT s.*, (SELECT COUNT(*) FROM listings l WHERE l.shop_id=s.shop_id) AS listing_count
                FROM monitored_shops s ORDER BY is_active DESC, shop_name COLLATE NOCASE""").fetchall()
        return render_template("favourite_shops.html", shops=shops, message=message)
