"""Houseplant diary checks (run with python -m unittest tests.test_houseplants)."""
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from favourite_feed import plants as module
from favourite_feed.web import app


class HouseplantTests(unittest.TestCase):
    def test_seed_and_watering(self):
        with TemporaryDirectory() as temp:
            with patch.object(module, "DB_PATH", Path(temp) / "plants.db"):
                client = app.test_client()
                response = client.get("/plants")
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"Cape sundew", response.data)
                with module.connection() as conn:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM houseplants").fetchone()[0], 17)
                headers = {"Origin": "https://localhost"}
                response = client.post("/plants/1/water", data={"watered_on": date.today().isoformat()},
                                       headers=headers, base_url="https://localhost")
                self.assertEqual(response.status_code, 303)
                with module.connection() as conn:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM plant_watering").fetchone()[0], 1)
                # Seeding is idempotent, including after deleting a plant.
                client.post("/plants/1/delete", headers=headers, base_url="https://localhost")
                with module.connection() as conn:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM houseplants").fetchone()[0], 16)

    def test_cross_origin_write_blocked(self):
        client = app.test_client()
        response = client.post("/plants/add", data={"name": "Fern", "species": "Button fern"},
                               headers={"Origin": "https://other.example"}, base_url="https://localhost")
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
