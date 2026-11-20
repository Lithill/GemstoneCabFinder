"""Opt-in private tracker preview registration and isolated test harness.

No health answers are transmitted or saved. The production app imports this
module only when HEALTH_TRACKER_PREVIEW_ENABLED=1 is explicitly configured.
"""
from flask import Flask, make_response, render_template

from favourite_feed.health_auth import health_auth, require_health_login


def register_private_preview(app):
    """Add login and protected preview routes to a Flask app, without write APIs."""
    app.register_blueprint(health_auth)

    @app.get("/private-symptom-tracker")
    @require_health_login
    def private_symptom_tracker():
        response = make_response(render_template("symptom_tracker.html", private_preview=True))
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


def create_staging_app():
    """Isolated Flask app for integration tests; not a production WSGI target."""
    app = Flask(__name__)
    register_private_preview(app)
    return app
