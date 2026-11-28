import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from favourite_feed import database
from favourite_feed.shop_management import add_shop
from favourite_feed.etsy_favourite_status import set_confirmed


class EtsyFavouriteStatusTests(unittest.TestCase):
    def test_confirm_and_undo_preserve_monitoring(self):
        with TemporaryDirectory() as tmp, patch.object(database,"DB_PATH",Path(tmp)/"test.db"):
            database.setup_database()
            with patch("favourite_feed.shop_management.find_shop_by_name",return_value={"shop_id":123,"shop_name":"ExampleShop"}):
                add_shop("ExampleShop")
            set_confirmed(123,True)
            set_confirmed(123,True)
            with database.connect_database() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM etsy_favourite_confirmations").fetchone()[0],1)
            set_confirmed(123,False)
            with database.connect_database() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM etsy_favourite_confirmations").fetchone()[0],0)
                self.assertEqual(conn.execute("SELECT is_active FROM monitored_shops WHERE shop_id=123").fetchone()[0],1)
            with self.assertRaises(ValueError):
                set_confirmed(999,True)
