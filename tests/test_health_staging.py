"""Integration tests for login-protected non-saving tracker preview."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from favourite_feed import health_auth
from favourite_feed.health_staging import create_staging_app
from favourite_feed.health_vault import password_hash


class PrivateTrackerIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        rate_patch = patch.object(health_auth, "RATE_DB", Path(temp.name) / "rate.db")
        rate_patch.start()
        self.addCleanup(rate_patch.stop)
        env = patch.dict(os.environ, {
            "HEALTH_SESSION_SECRET": "s" * 64,
            "HEALTH_VAULT_KEY": Fernet.generate_key().decode(),
            "HEALTH_PASSWORD_HASH": password_hash("integration test passphrase"),
        })
        env.start()
        self.addCleanup(env.stop)
        app = create_staging_app()
        app.config.update(TESTING=True, SERVER_NAME="localhost")
        self.client = app.test_client()

    def test_private_preview_has_no_health_write_routes(self):
        rules = list(self.client.application.url_map.iter_rules())
        private = [rule for rule in rules if rule.rule == "/private-symptom-tracker"]
        self.assertEqual(len(private), 1)
        self.assertEqual(private[0].methods - {"HEAD", "OPTIONS"}, {"GET"})
        self.assertFalse(any("/health" in rule.rule and
                             any(method in rule.methods for method in {"PUT", "PATCH", "DELETE"})
                             for rule in rules))
        self.assertEqual(self.client.post("/private-symptom-tracker",
                                         json={"answer": "private"}).status_code, 405)

    def test_anonymous_user_cannot_view_tracker(self):
        response = self.client.get("/private-symptom-tracker")
        self.assertEqual(response.status_code, 303)
        self.assertIn("/health-auth/login", response.headers["Location"])
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])

    def test_login_unlocks_tracker_and_logout_locks_it_again(self):
        login_page = self.client.get("/health-auth/login")
        self.assertEqual(login_page.status_code, 200)
        csrf = self.client.get_cookie("__Host-health_login_csrf").value
        response = self.client.post("/health-auth/login", data={
            "csrf": csrf, "password": "integration test passphrase"
        })
        self.assertEqual(response.status_code, 303)
        tracker = self.client.get("/private-symptom-tracker")
        self.assertEqual(tracker.status_code, 200)
        self.assertIn(b"symptom", tracker.data.lower())
        self.assertEqual(tracker.headers["Cache-Control"], "no-store")
        self.assertIn("form-action 'none'", tracker.headers["Content-Security-Policy"])
        session = self.client.get_cookie(health_auth.COOKIE).value
        logout_csrf = health_auth._signer("health-session-v1").loads(session)["csrf"]
        self.assertEqual(self.client.post("/health-auth/logout", data={"csrf": logout_csrf}).status_code, 303)
        self.assertEqual(self.client.get("/private-symptom-tracker").status_code, 303)

    def test_existing_session_is_rejected_if_security_config_disappears(self):
        self.client.get("/health-auth/login")
        csrf = self.client.get_cookie("__Host-health_login_csrf").value
        self.assertEqual(self.client.post("/health-auth/login", data={
            "csrf": csrf, "password": "integration test passphrase"
        }).status_code, 303)
        self.assertEqual(self.client.get("/private-symptom-tracker").status_code, 200)
        with patch.dict(os.environ, {"HEALTH_VAULT_KEY": "invalid-key"}):
            self.assertEqual(self.client.get("/private-symptom-tracker").status_code, 303)
        with patch.dict(os.environ, {"HEALTH_PASSWORD_HASH": ""}):
            self.assertEqual(self.client.get("/private-symptom-tracker").status_code, 303)

    def test_missing_credentials_cannot_view_tracker(self):
        with patch.dict(os.environ, {"HEALTH_PASSWORD_HASH": ""}):
            self.assertEqual(self.client.get("/private-symptom-tracker").status_code, 303)
            self.assertEqual(self.client.get("/health-auth/login").status_code, 503)


if __name__ == "__main__":
    unittest.main()
