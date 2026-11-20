"""Isolated login-to-tracker integration harness; never imported by live web.py.

This app is for automated security testing only. It never accepts or saves
health answers. Do not expose it publicly or deploy it as the production WSGI app.
"""
from flask import Flask, make_response, render_template

from favourite_feed.health_auth import health_auth, require_health_login


def create_staging_app():
    app = Flask(__name__)
    app.register_blueprint(health_auth)

    @app.get("/private-symptom-tracker")
    @require_health_login
    def private_symptom_tracker():
        response = make_response(render_template("symptom_tracker.html"))
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    return app
