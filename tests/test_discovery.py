import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from favourite_feed import database, discovery

class DiscoveryTests(unittest.TestCase):
    def test_terms(self):
        self.assertEqual(discovery.terms_from_text("opal\nopal\njasper"),["opal","jasper"])
        with self.assertRaises(ValueError):
            discovery.terms_from_text(" ")

    def test_queue_and_rejection(self):
        with TemporaryDirectory() as tmp, patch.object(database,"DB_PATH",Path(tmp)/"test.db"):
            database.setup_database()
            discovery.start()
            with patch.object(discovery,"etsy_get",return_value={"results":[{"shop_id":1,"listing_id":2,"title":"opal cabochon"}]}):
                discovery.step()
            with patch.object(discovery,"etsy_get",return_value={"shop_name":"Example","review_average":5,"review_count":100,"create_date":100,"shipping_from_country_iso":"GB"}):
                discovery.step()
            discovery.review(1,"reject")
            with database.connect_database() as conn:
                self.assertEqual(conn.execute("SELECT status FROM discovery_shops").fetchone()[0],"reject")
            with patch.object(discovery,"etsy_get",return_value={"results":[{"shop_id":1,"listing_id":2,"title":"opal cabochon"}]}):
                discovery.step()
            with database.connect_database() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM discovery_queue").fetchone()[0],0)
