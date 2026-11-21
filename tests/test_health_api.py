"""End-to-end fictional-data tests for the DOUBLE-OPT-IN private staging API."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from favourite_feed import health_auth, health_vault
from favourite_feed.health_staging import create_staging_app
from favourite_feed.health_vault import password_hash


class PrivateStagingWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "fictional-private.db"
        rate = patch.object(health_auth, "RATE_DB", Path(temp.name) / "login-limits.db")
        rate.start()
        self.addCleanup(rate.stop)
        env = patch.dict(os.environ, {
            "HEALTH_SESSION_SECRET": "x" * 64,
            "HEALTH_VAULT_KEY": Fernet.generate_key().decode(),
            "HEALTH_PASSWORD_HASH": password_hash("staging-only long passphrase"),
            "HEALTH_STAGING_STORAGE_ENABLED": "1",
            "HEALTH_STAGING_VAULT_PATH": str(self.path),
        })
        env.start()
        self.addCleanup(env.stop)
        health_vault.provision(self.path)
        app = create_staging_app()
        app.config.update(TESTING=True, SERVER_NAME="localhost")
        self.client = app.test_client()

    def login(self):
        self.client.get("/health-auth/login")
        csrf = self.client.get_cookie("__Host-health_login_csrf").value
        self.assertEqual(self.client.post("/health-auth/login", data={
            "csrf": csrf, "password": "staging-only long passphrase"
        }).status_code, 303)
        session = self.client.get("/private-health-api/session")
        self.assertEqual(session.status_code, 200)
        return session.json["csrf"]

    def test_login_save_load_edit_delete_logout(self):
        day = "2026-11-21"
        endpoint = "/private-health-api/checkin/" + day
        self.assertEqual(self.client.get(endpoint).status_code, 401)
        csrf = self.login()
        self.assertIn(b"staging-save", self.client.get("/private-symptom-tracker").data)
        self.assertEqual(self.client.post(endpoint, json={"entries":[]}).status_code, 403)
        headers = {"X-Health-CSRF": csrf}
        entries = [
            {"name":"Brain fog","answer":"Mild","extras":[],"notes":"never store"},
            {"name":"Weight measurement","answer":"65.2","extras":["unit: kg"],"notes":""},
        ]
        saved = self.client.post(endpoint, json={"entries": entries}, headers=headers)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json["saved"], 2)
        loaded = self.client.get(endpoint)
        self.assertEqual(loaded.status_code, 200)
        self.assertEqual(len(loaded.json["entries"]), 2)
        self.assertTrue(all(entry["notes"] == "" for entry in loaded.json["entries"]))
        self.assertNotIn(b"never store", self.path.read_bytes())
        edited = self.client.post(endpoint, json={"entries":[{
            "name":"Brain fog","answer":"Severe","extras":[],"notes":""
        }]}, headers=headers)
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(len(self.client.get(endpoint).json["entries"]), 2)
        deleted = self.client.post("/private-health-api/delete/" + day,
                                   json={"question":"Brain fog"}, headers=headers)
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.json["deleted"])
        self.assertEqual(len(self.client.get(endpoint).json["entries"]), 1)
        token = self.client.get_cookie(health_auth.COOKIE).value
        logout_csrf = health_auth._signer("health-session-v1").loads(token)["csrf"]
        self.assertEqual(self.client.post("/health-auth/logout", data={"csrf": logout_csrf}).status_code, 303)
        self.assertEqual(self.client.get(endpoint).status_code, 401)
        self.assertEqual(self.client.post(endpoint, json={"entries":[]}, headers=headers).status_code, 401)

    def test_invalid_submission_does_not_partially_save(self):
        csrf = self.login()
        response = self.client.post("/private-health-api/checkin/2026-11-21", headers={"X-Health-CSRF":csrf},
                                    json={"entries":[
                                        {"name":"Brain fog","answer":"Mild","extras":[],"notes":""},
                                        {"name":"Period / bleeding today","answer":"Period","extras":["flow: []"],"notes":""},
                                    ]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/private-health-api/checkin/2026-11-21").json["entries"], [])

    def test_storage_disabled_by_default_in_preview(self):
        with patch.dict(os.environ, {"HEALTH_STAGING_STORAGE_ENABLED": "0"}):
            app = create_staging_app()
            app.config.update(TESTING=True, SERVER_NAME="localhost")
            client = app.test_client()
            self.assertEqual(client.get("/private-health-api/session").status_code, 404)
            self.assertNotIn(b"staging-save", client.get("/private-symptom-tracker").data)


if __name__ == "__main__":
    unittest.main()
