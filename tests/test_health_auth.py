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
    def tearDownClass(cls):
        cls.env.stop()
        cls.limits.stop()
        cls.temp.cleanup()

    def setUp(self):
        self.client = self.app.test_client()
        self.login_csrf = self._get_csrf()

    def _get_csrf(self):
        response = self.client.get("/health-auth/login")
        self.assertEqual(response.status_code, 200)
        cookie = self.client.get_cookie("__Host-health_login_csrf")
        self.assertIsNotNone(cookie)
        return cookie.value

    def _login(self, password="a strong test password 123", csrf=None):
        return self.client.post("/health-auth/login", data={"password": password, "csrf": csrf if csrf is not None else self.login_csrf})

    def test_login_requires_csrf(self):
        self.assertEqual(self._login(csrf="invalid").status_code, 400)

    def test_wrong_password_is_rejected(self):
        self.assertEqual(self._login("wrong password").status_code, 401)
        self.assertIsNone(self.client.get_cookie("__Host-health_session"))

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

    def test_logout_requires_csrf(self):
        self.assertEqual(self._login().status_code, 303)
        self.assertEqual(self.client.post("/health-auth/logout", data={"csrf": "wrong"}).status_code, 400)
        self.assertEqual(self.client.get("/health-auth/").status_code, 200)

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

    def test_missing_configuration_refuses_login(self):
        with patch.dict(os.environ, {"HEALTH_PASSWORD_HASH": ""}):
            self.assertEqual(self.client.get("/health-auth/login").status_code, 503)

    def test_invalid_encryption_key_refuses_login(self):
        with patch.dict(os.environ, {"HEALTH_VAULT_KEY": "invalid-key"}):
            self.assertEqual(self.client.get("/health-auth/login").status_code, 503)

    def test_short_session_secret_refuses_login(self):
        with patch.dict(os.environ, {"HEALTH_SESSION_SECRET": "too-short"}):
            self.assertEqual(self.client.get("/health-auth/login").status_code, 503)

    def test_session_is_http_only_secure_and_same_site_strict(self):
        response = self._login()
        cookie = next(v for v in response.headers.getlist("Set-Cookie") if "__Host-health_session=" in v)
        self.assertIn("Secure", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertEqual(response.headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
