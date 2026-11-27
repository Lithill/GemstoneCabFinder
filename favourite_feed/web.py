"""Personal dashboard application entry point.

Deploy behind HTTPS and site authentication.
"""
import os
from threading import Lock
from flask import Flask, render_template, redirect
from favourite_feed.database import setup_database
from favourite_feed.plants import plants as plants_blueprint
from favourite_feed.feed_routes import register_feed_routes, preferences, feed_breakdown, ensure_history
from favourite_feed.refresh_routes import register_refresh_routes
from favourite_feed.seller_routes import register_seller_routes
from favourite_feed.quiz_routes import register_quiz_routes

# Create the Flask application that PythonAnywhere imports to serve the website.
app = Flask(__name__)
# Attach the houseplant section, which defines its own group of URLs.
app.register_blueprint(plants_blueprint)
# Share a lock between seller management and refresh routes to prevent overlapping locked operations within this process.
refresh_lock = Lock()

# Only attach the private health pages when explicitly enabled in the environment.
if os.environ.get("HEALTH_TRACKER_PREVIEW_ENABLED") == "1":
    from favourite_feed.health_staging import register_private_preview
    register_private_preview(app)


# Tell browsers not to store responses, so pages show current data rather than cached copies.
@app.after_request
def prevent_stale_feed(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/symptom-tracker")
def symptom_tracker():
    """Read-only prototype: no health data is accepted or stored."""
    if os.environ.get("HEALTH_TRACKER_PREVIEW_ENABLED") == "1":
        return redirect("/private-symptom-tracker")
    response = app.make_response(render_template("symptom_tracker.html"))
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'"
    return response


# Connect each section's functions to its website addresses.
register_feed_routes(app)
register_refresh_routes(app, refresh_lock)
register_seller_routes(app, refresh_lock)
register_quiz_routes(app)


# Start a local development server only when this file is executed directly.
if __name__ == "__main__":
    setup_database()
    app.run(host="127.0.0.1", port=5000, debug=False)
