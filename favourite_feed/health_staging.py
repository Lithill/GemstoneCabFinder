"""Opt-in private tracker preview registration and isolated test harness.

No health answers are transmitted or saved. The production app imports this
module only when HEALTH_TRACKER_PREVIEW_ENABLED=1 is explicitly configured.
"""
from flask import Flask, make_response, render_template
import os

from favourite_feed.health_auth import health_auth, require_health_login, site_auth_mode


# Register private pages and the API; the storage and personal-diary switches control enabled features.
def register_private_preview(app):
    """Add login and protected preview routes to a Flask app, without write APIs."""
    # Only register the separate tracker login when site-wide authentication is not selected.
    if not site_auth_mode():
        app.register_blueprint(health_auth)
    from favourite_feed.health_api import register_staging_api
    register_staging_api(app)

    # Require the configured access check before rendering the private diary page.
    @app.get("/private-symptom-tracker")
    @require_health_login
    def private_symptom_tracker():
        response = make_response(render_template("symptom_tracker.html", private_preview=True, site_auth=site_auth_mode(), personal_diary=os.environ.get("HEALTH_PERSONAL_DIARY_ENABLED") == "1", storage_staging=os.environ.get("HEALTH_STAGING_STORAGE_ENABLED") == "1"))
        # Discourage browser caching and restrict resource loading, framing and referrer disclosure.
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


# Build an isolated application for automated tests rather than using the deployed dashboard.
def create_staging_app():
    """Isolated Flask app for integration tests; not a production WSGI target."""
    app = Flask(__name__)
    register_private_preview(app)
    return app
