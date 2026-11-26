import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet
from favourite_feed.health_staging import create_staging_app
from favourite_feed.health_vault import provision

class SiteAuthTests(unittest.TestCase):
    def test_site_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "fictional.db"
            with patch.dict(os.environ, {
                "HEALTH_SITE_AUTH_ENABLED": "1",
                "HEALTH_STAGING_STORAGE_ENABLED": "1",
                "HEALTH_STAGING_VAULT_PATH": str(vault),
                "HEALTH_VAULT_KEY": Fernet.generate_key().decode(),
                "HEALTH_SESSION_SECRET": "s" * 64,
                "HEALTH_PASSWORD_HASH": "",
            }):
                provision(vault)
                app = create_staging_app()
                app.config.update(TESTING=True)
                client = app.test_client()
                https = "https://localhost"
                self.assertEqual(client.get("/private-health-api/session").status_code, 401)
                self.assertEqual(client.get("/health-auth/login", base_url=https).status_code, 404)
                self.assertEqual(client.get("/private-symptom-tracker", base_url=https).status_code, 200)
                token = client.get("/private-health-api/session", base_url=https).json["csrf"]
                endpoint = "/private-health-api/checkin/2026-11-26"
                payload = {"entries": [{"name": "Brain fog", "answer": "Mild", "extras": [], "notes": ""}]}
                headers = {"X-Health-CSRF": token}
                self.assertEqual(client.post(endpoint, base_url=https, json=payload, headers=headers).status_code, 403)
                headers["Origin"] = "https://other.example"
                self.assertEqual(client.post(endpoint, base_url=https, json=payload, headers=headers).status_code, 403)
                headers["Origin"] = https
                self.assertEqual(client.post(endpoint, base_url=https, json=payload, headers=headers).status_code, 200)
                self.assertEqual(len(client.get(endpoint, base_url=https).json["entries"]), 1)
                with patch.dict(os.environ, {"HEALTH_SESSION_SECRET": ""}):
                    self.assertEqual(client.get(endpoint, base_url=https).status_code, 401)
