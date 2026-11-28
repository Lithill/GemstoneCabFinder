"""Houseplant diary checks (run with python -m unittest tests.test_houseplants)."""
from contextlib import closing
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from favourite_feed import plants as module
from favourite_feed.web import app


class HouseplantTests(unittest.TestCase):
    # Use a temporary plant database and Flask test client to check initial seeding and watering.
    def test_seed_and_watering(self):
        with TemporaryDirectory() as temp:
            with patch.object(module, "DB_PATH", Path(temp) / "plants.db"):
                client = app.test_client()
                response = client.get("/plants")
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"Cape sundew", response.data)
                with closing(module.connection()) as conn:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM houseplants").fetchone()[0], 17)
                # Supply a matching origin for legitimate simulated form submissions.
                headers = {"Origin": "https://localhost"}
                # Record watering for the first plant and expect a redirect.
                response = client.post("/plants/1/water", data={"watered_on": date.today().isoformat()},
                                       headers=headers, base_url="https://localhost")
                self.assertEqual(response.status_code, 303)
                with closing(module.connection()) as conn:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM plant_watering").fetchone()[0], 1)
                response = client.post("/plants/1/water", data={"watered_on": date.today().isoformat()},
                                       headers=headers, base_url="https://localhost")
                self.assertEqual(response.status_code, 303)
                with closing(module.connection()) as conn:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM plant_watering").fetchone()[0], 1)
                # The repeated watering submission above must leave only one record for the day.
                # Seeding is idempotent, including after deleting a plant.
                client.post("/plants/1/delete", headers=headers, base_url="https://localhost")
                with closing(module.connection()) as conn:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM houseplants").fetchone()[0], 16)

    def test_moisture_and_history(self):
        with TemporaryDirectory() as temp, patch.object(module, "DB_PATH", Path(temp)/"plants.db"):
            client = app.test_client()
            client.get("/plants")
            headers = {"Origin": "https://localhost"}
            for day in ("2020-01-01", "2020-01-11"):
                self.assertEqual(client.post("/plants/1/water", data={"watered_on":day}, headers=headers, base_url="https://localhost").status_code,303)
            for state in ("Wet","Moist"):
                response = client.post("/plants/1/moisture", data={"checked_on":"2020-01-12","moisture":state}, headers=headers, base_url="https://localhost")
                self.assertEqual(response.status_code,303)
            with closing(module.connection()) as conn:
                self.assertEqual(conn.execute("SELECT moisture FROM plant_moisture").fetchone()[0],"Moist")
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM plant_moisture").fetchone()[0],1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM plant_watering").fetchone()[0],2)
            page = client.get("/plants")
            self.assertIn(b"Average interval: 10",page.data)
            self.assertIn(b"2020-01-12",page.data)
            self.assertEqual(client.post("/plants/1/moisture",data={"checked_on":"2020-01-12","moisture":"invalid"},headers=headers,base_url="https://localhost").status_code,400)
            self.assertEqual(client.post("/plants/1/moisture",data={"checked_on":"2020-01-12","moisture":"Wet"},headers={"Origin":"https://other.example"},base_url="https://localhost").status_code,403)

    # A form submission from another origin must be rejected with HTTP 403.
    def test_cross_origin_write_blocked(self):
        client = app.test_client()
        response = client.post("/plants/add", data={"name": "Fern", "species": "Button fern"},
                               headers={"Origin": "https://other.example"}, base_url="https://localhost")
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
