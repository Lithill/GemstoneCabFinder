"""Security regression tests for the UNREGISTERED health login blueprint.

Run locally: python -m unittest discover -s tests -p 'test_health_auth.py'
Requires Flask, cryptography and itsdangerous.
"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask
from cryptography.fernet import Fernet
from favourite_feed import health_auth
from favourite_feed.health_vault import password_hash


class HealthLoginTests(unittest.TestCase):
    @classmethod
    # Build an isolated Flask application for the legacy login blueprint with fictional credentials and a temporary rate-limit database.
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.limits = patch.object(health_auth, "RATE_DB", Path(cls.temp.name) / "limits.db")
        cls.limits.start()
        cls.env = patch.dict(os.environ, {
            "HEALTH_SESSION_SECRET": "a" * 64,
            "HEALTH_VAULT_KEY": Fernet.generate_key().decode(),
            "HEALTH_PASSWORD_HASH": password_hash("a strong test password 123"),
        })
        cls.env.start()
        cls.app = Flask(__name__)
        cls.app.config.update(TESTING=True, SERVER_NAME="localhost")
        cls.app.register_blueprint(health_auth.health_auth)

    @classmethod
    # Restore patched settings and remove temporary files after the class finishes.
    def tearDownClass(cls):
        cls.env.stop()
        cls.limits.stop()
        cls.temp.cleanup()

    # Create a fresh browser-like test client and obtain its login CSRF cookie.
    def setUp(self):
        self.client = self.app.test_client()
        self.login_csrf = self._get_csrf()

    # Request the login page and read its anti-forgery cookie.
    def _get_csrf(self):
        response = self.client.get("/health-auth/login")
        self.assertEqual(response.status_code, 200)
        cookie = self.client.get_cookie("__Host-health_login_csrf")
        self.assertIsNotNone(cookie)
        return cookie.value

    # Submit a simulated login using the test password and CSRF token unless overridden.
    def _login(self, password="a strong test password 123", csrf=None):
        return self.client.post("/health-auth/login", data={"password": password, "csrf": csrf if csrf is not None else self.login_csrf})

    # Track database connections through login, protected page access and logout to verify cleanup.
    def test_login_and_logout_close_rate_limit_connections(self):
        original_connection = health_auth._rate_connection
        opened = []

        class TrackedConnection:
            def __init__(self, connection):
                self.connection = connection
                self.closed = False

            def __getattr__(self, name):
                return getattr(self.connection, name)

            def __enter__(self):
                self.connection.__enter__()
                return self

            def __exit__(self, *args):
                return self.connection.__exit__(*args)

            def close(self):
                self.closed = True
                self.connection.close()

        def tracked_connection():
            tracked = TrackedConnection(original_connection())
            opened.append(tracked)
            return tracked

        with patch.object(health_auth, "_rate_connection", side_effect=tracked_connection):
            self.assertEqual(self._login().status_code, 303)
            self.assertEqual(self.client.get("/health-auth/").status_code, 200)
            session = self.client.get_cookie("__Host-health_session")
            csrf = health_auth._signer("health-session-v1").loads(session.value)["csrf"]
            self.assertEqual(self.client.post("/health-auth/logout", data={"csrf": csrf}).status_code, 303)
            self.assertEqual(self.client.get("/health-auth/").status_code, 303)
        self.assertGreaterEqual(len(opened), 4)
        self.assertTrue(all(connection.closed for connection in opened))

    # A correctly signed token with an invalid payload must not grant access.
    def test_signed_but_malformed_session_payload_fails_closed(self):
        for payload in ([], "not-a-session", 42, {"auth": True, "csrf": [], "nonce": "x"}):
            with self.subTest(payload=payload):
                token = health_auth._signer("health-session-v1").dumps(payload)
                self.client.set_cookie(health_auth.COOKIE, token, domain="localhost")
                self.assertEqual(self.client.get("/health-auth/").status_code, 303)
        self.client.delete_cookie(health_auth.COOKIE, domain="localhost")

    # Reject login submissions with an invalid anti-forgery token.
    def test_login_requires_csrf(self):
        self.assertEqual(self._login(csrf="invalid").status_code, 400)

    # An incorrect password must not create an authenticated session.
    def test_wrong_password_is_rejected(self):
        self.assertEqual(self._login("wrong password").status_code, 401)
        self.assertIsNone(self.client.get_cookie("__Host-health_session"))

    # Verify login grants access and logout revokes even a replayed copy of the old cookie.
    def test_successful_login_and_logout_revoke_session(self):
        self.assertEqual(self._login().status_code, 303)
        cookie = self.client.get_cookie("__Host-health_session")
        self.assertIsNotNone(cookie)
        self.assertEqual(self.client.get("/health-auth/").status_code, 200)
        csrf = health_auth._signer("health-session-v1").loads(cookie.value)["csrf"]
        self.assertEqual(self.client.post("/health-auth/logout", data={"csrf": csrf}).status_code, 303)
        self.assertEqual(self.client.get("/health-auth/").status_code, 303)
        self.client.set_cookie("__Host-health_session", cookie.value, domain="localhost")
        self.assertEqual(self.client.get("/health-auth/").status_code, 303)

    # Reject invalid logout requests without ending the valid session.
    def test_logout_requires_csrf(self):
        self.assertEqual(self._login().status_code, 303)
        self.assertEqual(self.client.post("/health-auth/logout", data={"csrf": "wrong"}).status_code, 400)
        self.assertEqual(self.client.get("/health-auth/").status_code, 200)

    # Five failed attempts trigger a temporary lockout even when the next password is correct.
    def test_repeated_failed_passwords_lock_out_login(self):
        # A distinct client address avoids influencing other test cases.
        address = "198.51.100.23"
        for _ in range(5):
            response = self.client.post(
                "/health-auth/login",
                data={"password": "wrong", "csrf": self.login_csrf},
                environ_overrides={"REMOTE_ADDR": address},
            )
            self.assertEqual(response.status_code, 401)
        response = self.client.post(
            "/health-auth/login",
            data={"password": "a strong test password 123", "csrf": self.login_csrf},
            environ_overrides={"REMOTE_ADDR": address},
        )
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)

    # Reject excessive password input before invoking the expensive hashing operation.
    def test_oversized_password_is_rejected_before_hashing(self):
        with patch.object(health_auth, "check_password", side_effect=AssertionError("hashing must not run")):
            response = self._login("x" * 1025)
        self.assertEqual(response.status_code, 413)

    # Refuse login when the password hash is absent.
    def test_missing_configuration_refuses_login(self):
        with patch.dict(os.environ, {"HEALTH_PASSWORD_HASH": ""}):
            self.assertEqual(self.client.get("/health-auth/login").status_code, 503)

    # Refuse login with an invalid vault key.
    def test_invalid_encryption_key_refuses_login(self):
        with patch.dict(os.environ, {"HEALTH_VAULT_KEY": "invalid-key"}):
            self.assertEqual(self.client.get("/health-auth/login").status_code, 503)

    # Refuse login when the signing secret is too short.
    def test_short_session_secret_refuses_login(self):
        with patch.dict(os.environ, {"HEALTH_SESSION_SECRET": "too-short"}):
            self.assertEqual(self.client.get("/health-auth/login").status_code, 503)

    # Check secure cookie attributes and the no-store response header.
    def test_session_is_http_only_secure_and_same_site_strict(self):
        response = self._login()
        cookie = next(v for v in response.headers.getlist("Set-Cookie") if "__Host-health_session=" in v)
        self.assertIn("Secure", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertEqual(response.headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
