import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path
from favourite_feed import database
from favourite_feed.shop_management import shop_name, add_shop, import_recent

class ShopManagementTests(unittest.TestCase):
    # Accept a plain shop name or valid Etsy shop URL and reject unrelated URLs and paths.
    def test_names(self):
        self.assertEqual(shop_name("ExampleShop"),"ExampleShop")
        self.assertEqual(shop_name("https://www.etsy.com/uk/shop/ExampleShop?ref=test"),"ExampleShop")
        for value in ("https://example.com/shop/Test","https://www.etsy.com/listing/123","../Test"):
            with self.assertRaises(ValueError):
                shop_name(value)

    # Use a temporary database and simulated lookups to verify adding and importing are idempotent.
    def test_add_and_import(self):
        with TemporaryDirectory() as tmp, patch.object(database,"DB_PATH",Path(tmp)/"test.db"):
            database.setup_database()
            with patch("favourite_feed.shop_management.find_shop_by_name",return_value={"shop_id":123,"shop_name":"ExampleShop"}):
                self.assertEqual(add_shop("ExampleShop"),(123,True))
                self.assertEqual(add_shop("ExampleShop"),(123,False))
            # Provide a fictional listing and mock both listing and image API calls.
            listing={"listing_id":456,"title":"Example","creation_timestamp":100,"original_creation_timestamp":90}
            with patch("favourite_feed.shop_management.etsy_get",return_value={"results":[listing]}), patch("favourite_feed.refresh.etsy_get",return_value={"results":[]}):
                self.assertEqual(import_recent(123,5),1)
                self.assertEqual(import_recent(123,5),0)
            with database.connect_database() as conn:
                # Check that the new shop baseline matches its initial last-checked time and only one listing exists.
                row=conn.execute("SELECT * FROM monitored_shops").fetchone()
                self.assertEqual(row["baseline_at"],row["last_checked"])
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0],1)

    # Reject a resolved shop whose ID differs from the expected seller ID, leaving the database empty.
    def test_identity_mismatch_does_not_insert(self):
        with TemporaryDirectory() as tmp, patch.object(database,"DB_PATH",Path(tmp)/"test.db"):
            database.setup_database()
            with patch("favourite_feed.shop_management.find_shop_by_name",return_value={"shop_id":123,"shop_name":"ExampleShop"}):
                with self.assertRaises(ValueError):
                    add_shop("ExampleShop", expected_id=999)
            with database.connect_database() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM monitored_shops").fetchone()[0],0)
