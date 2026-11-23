"""Basic safety checks for the separate houseplant diary."""
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash
from favourite_feed import plants as module
from favourite_feed.web import app


class HouseplantTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_unconfigured_routes_are_closed(self):
        with patch.dict("os.environ", {"PLANTS_PASSWORD_HASH": ""}):
            self.assertEqual(self.client.get("/plants").status_code, 503)
            self.assertEqual(self.client.post("/plants/add").status_code, 503)

    def test_password_required(self):
        with patch.dict("os.environ", {"PLANTS_PASSWORD_HASH": generate_password_hash("test-password")}):
            self.assertEqual(self.client.get("/plants").status_code, 401)

    def test_watering_is_recorded_separately(self):
        with TemporaryDirectory() as temp:
            with patch.object(module, "DB_PATH", Path(temp) / "plants.db"):
                with patch.dict("os.environ", {"PLANTS_PASSWORD_HASH": generate_password_hash("test-password")}):
                    headers = {"Authorization": "Basic cGxhbnRzOnRlc3QtcGFzc3dvcmQ=", "Origin": "https://localhost"}
                    self.assertEqual(self.client.post("/plants/add", data={"name": "Kitchen fern", "species": "Other / not sure"}, headers=headers, base_url="https://localhost").status_code, 303)
                    self.assertEqual(self.client.post("/plants/1/water", data={"watered_on": date.today().isoformat()}, headers=headers, base_url="https://localhost").status_code, 303)
                    response = self.client.get("/plants", headers=headers, base_url="https://localhost")
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(b"Kitchen fern", response.data)
                    self.assertIn(date.today().isoformat().encode(), response.data)

    def test_cross_origin_write_blocked(self):
        with patch.dict("os.environ", {"PLANTS_PASSWORD_HASH": generate_password_hash("test-password")}):
            response = self.client.post("/plants/add", data={"name": "Fern", "species": "Other / not sure"},
                                        headers={"Authorization": "Basic cGxhbnRzOnRlc3QtcGFzc3dvcmQ=", "Origin": "https://other.example"},
                                        base_url="https://localhost")
            self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
