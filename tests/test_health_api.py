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
    # Configure a temporary fictional vault and legacy login test client with cleanup registered.
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

    # Simulate login and obtain the API anti-forgery token.
    def login(self):
        self.client.get("/health-auth/login")
        csrf = self.client.get_cookie("__Host-health_login_csrf").value
        self.assertEqual(self.client.post("/health-auth/login", data={
            "csrf": csrf, "password": "staging-only long passphrase"
        }).status_code, 303)
        session = self.client.get("/private-health-api/session")
        self.assertEqual(session.status_code, 200)
        return session.json["csrf"]

    # Exercise the full authenticated diary lifecycle, including omitted notes and access revocation.
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

    # Check monthly timeline privacy, explicit rest and no bleeding, missing days and dated lifestyle changes.
    def test_month_timeline_private_and_distinguishes_missing(self):
        endpoint = "/private-health-api/month/2026-02"
        self.assertEqual(self.client.get(endpoint).status_code, 401)
        self.login()
        health_vault.put("2026-02-02", "exercise-log-v1", {"rest": True, "sessions": []}, path=self.path)
        health_vault.put("2026-02-03", "Period / bleeding today", {"answer": "None"}, path=self.path)
        health_vault.put("0001-01-01", "ongoing-factors-v1", {"items": [
            {"name":"Example habit","category":"Other","history":[
                {"day":"2026-01-01","status":"Ongoing","dose":""},
                {"day":"2026-02-04","status":"Stopped","dose":""}]}]}, path=self.path)
        response = self.client.get(endpoint)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        data = response.json
        self.assertEqual(len(data["timeline"]), 28)
        self.assertIsNone(data["timeline"]["2026-02-01"]["exercise"])
        self.assertTrue(data["timeline"]["2026-02-02"]["exercise"]["rest"])
        self.assertEqual(data["timeline"]["2026-02-03"]["period"], "None")
        self.assertEqual(data["baseline"][0]["status"], "Ongoing")
        self.assertEqual(data["timeline"]["2026-02-04"]["changes"][0]["status"], "Stopped")
        self.assertNotIn("2026-02-02", data["days"])

    # Require authentication, no-store caching policy and a supported report duration.
    def test_report_requires_auth_and_is_not_cached(self):
        endpoint = "/private-health-api/report/30"
        self.assertEqual(self.client.get(endpoint).status_code, 401)
        self.login()
        response = self.client.get(endpoint)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn(b"Health Tracker", response.data)
        self.assertIn(b"No severity ratings recorded", response.data)
        self.assertEqual(self.client.get("/private-health-api/report/365").status_code, 400)

    # An invalid answer in a batch must leave the diary empty.
    def test_invalid_submission_does_not_partially_save(self):
        csrf = self.login()
        response = self.client.post("/private-health-api/checkin/2026-11-21", headers={"X-Health-CSRF":csrf},
                                    json={"entries":[
                                        {"name":"Brain fog","answer":"Mild","extras":[],"notes":""},
                                        {"name":"Period / bleeding today","answer":"Period","extras":["flow: []"],"notes":""},
                                    ]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/private-health-api/checkin/2026-11-21").json["entries"], [])

    # Disable storage and verify existing sessions cannot use the API until re-enabled.
    def test_disabling_storage_switch_revokes_existing_api_access(self):
        csrf = self.login()
        endpoint = "/private-health-api/checkin/2026-11-21"
        with patch.dict(os.environ, {"HEALTH_STAGING_STORAGE_ENABLED": "0"}):
            self.assertEqual(self.client.get(endpoint).status_code, 404)
            self.assertEqual(self.client.post(endpoint, json={"entries":[]},
                                              headers={"X-Health-CSRF":csrf}).status_code, 404)
        self.assertEqual(self.client.get(endpoint).status_code, 200)

    # Reject the reserved database filenames used in these test cases.
    def test_staging_path_cannot_target_production_vault(self):
        csrf = self.login()
        endpoint = "/private-health-api/checkin/2026-11-21"
        for unsafe in ("health_vault.db", "favourite_feed.db"):
            with self.subTest(path=unsafe):
                with patch.dict(os.environ, {"HEALTH_STAGING_VAULT_PATH":str(self.path.parent / unsafe)}):
                    self.assertEqual(self.client.post(endpoint, json={"entries":[]},
                                                      headers={"X-Health-CSRF":csrf}).status_code, 503)

    # With storage explicitly disabled, hide save controls and return 404 for the session endpoint.
    def test_storage_disabled_by_default_in_preview(self):
        with patch.dict(os.environ, {"HEALTH_STAGING_STORAGE_ENABLED": "0"}):
            app = create_staging_app()
            app.config.update(TESTING=True, SERVER_NAME="localhost")
            client = app.test_client()
            self.assertEqual(client.get("/private-health-api/session").status_code, 404)
            self.assertNotIn(b"staging-save", client.get("/private-symptom-tracker").data)


if __name__ == "__main__":
    unittest.main()
