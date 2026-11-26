import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path
from favourite_feed import database
from favourite_feed.shop_management import shop_name, add_shop, import_recent

class ShopManagementTests(unittest.TestCase):
    def test_names(self):
        self.assertEqual(shop_name("ExampleShop"),"ExampleShop")
        self.assertEqual(shop_name("https://www.etsy.com/uk/shop/ExampleShop?ref=test"),"ExampleShop")
        for value in ("https://example.com/shop/Test","https://www.etsy.com/listing/123","../Test"):
            with self.assertRaises(ValueError):
                shop_name(value)

    def test_add_and_import(self):
        with TemporaryDirectory() as tmp, patch.object(database,"DB_PATH",Path(tmp)/"test.db"):
            database.setup_database()
            with patch("favourite_feed.shop_management.find_shop_by_name",return_value={"shop_id":123,"shop_name":"ExampleShop"}):
                self.assertEqual(add_shop("ExampleShop"),(123,True))
                self.assertEqual(add_shop("ExampleShop"),(123,False))
            listing={"listing_id":456,"title":"Example","creation_timestamp":100,"original_creation_timestamp":90}
            with patch("favourite_feed.shop_management.etsy_get",return_value={"results":[listing]}), patch("favourite_feed.refresh.etsy_get",return_value={"results":[]}):
                self.assertEqual(import_recent(123,5),1)
                self.assertEqual(import_recent(123,5),0)
            with database.connect_database() as conn:
                row=conn.execute("SELECT * FROM monitored_shops").fetchone()
                self.assertEqual(row["baseline_at"],row["last_checked"])
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0],1)
