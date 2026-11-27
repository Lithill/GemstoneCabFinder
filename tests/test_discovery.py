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

    def test_checked_seller_cache(self):
        with TemporaryDirectory() as tmp, patch.object(database,"DB_PATH",Path(tmp)/"test.db"), patch.object(discovery,"legacy_exclusions",return_value=(set(),set())):
            database.setup_database()
            discovery.start()
            listing={"shop_id":1,"listing_id":2,"title":"opal cabochon"}
            with patch.object(discovery,"etsy_get",return_value={"results":[listing]}):
                discovery.step()
            with patch.object(discovery,"etsy_get",return_value={"shop_name":"Example","review_average":2,"review_count":100,"create_date":100}):
                discovery.step()
            with patch.object(discovery,"etsy_get",return_value={"results":[listing]}) as api:
                discovery.step()
                self.assertEqual(api.call_args.args[0],"listings/active")
            with database.connect_database() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM discovery_queue").fetchone()[0],0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM discovery_checked").fetchone()[0],1)

    def test_stronger_evidence_and_history(self):
        with TemporaryDirectory() as tmp, patch.object(database,"DB_PATH",Path(tmp)/"test.db"), patch.object(discovery,"legacy_exclusions",return_value=({1,9},set())):
            database.setup_database()
            discovery.start()
            with database.connect_database() as conn:
                conn.execute("INSERT INTO discovery_shops(shop_id,name,evidence) VALUES(1,'Pending','Needs checking')")
            listings=[{"shop_id":1,"listing_id":3,"title":"opal cabochon exact stone pictured"},
                      {"shop_id":9,"listing_id":4,"title":"opal cabochon"}]
            with patch.object(discovery,"etsy_get",return_value={"results":listings}):
                discovery.step()
            with database.connect_database() as conn:
                row=conn.execute("SELECT evidence,listing_id,status FROM discovery_shops WHERE shop_id=1").fetchone()
                self.assertEqual(tuple(row),("Likely WYSIWYG",3,"pending"))
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM discovery_queue").fetchone()[0],0)

    def test_import_preserves_decisions(self):
        from favourite_feed import import_review_list
        with TemporaryDirectory() as tmp, patch.object(database,"DB_PATH",Path(tmp)/"test.db"):
            database.setup_database()
            with database.connect_database() as conn:
                discovery.setup(conn)
                conn.execute("INSERT INTO discovery_shops(shop_id,name,status) VALUES(60611701,'MpGemsIndia','reject')")
                conn.execute("INSERT INTO monitored_shops(shop_id,shop_name,shop_url,added_at) VALUES(61104361,'InfinityCabochons','https://www.etsy.com/shop/InfinityCabochons','2026-01-01')")
            import_review_list.main()
            import_review_list.main()
            with database.connect_database() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM discovery_shops").fetchone()[0],79)
                self.assertEqual(conn.execute("SELECT status FROM discovery_shops WHERE shop_id=60611701").fetchone()[0],"reject")
                self.assertIsNone(conn.execute("SELECT 1 FROM discovery_shops WHERE shop_id=61104361").fetchone())

    def test_missing_shop_does_not_block_queue(self):
        from requests import Response
        from requests.exceptions import HTTPError
        with TemporaryDirectory() as tmp, patch.object(database,"DB_PATH",Path(tmp)/"test.db"):
            database.setup_database()
            discovery.start()
            with database.connect_database() as conn:
                conn.execute("INSERT INTO discovery_queue VALUES(1,'Needs checking',2)")
            response = Response()
            response.status_code = 503
            with patch.object(discovery,"etsy_get",side_effect=HTTPError(response=response)):
                with self.assertRaises(HTTPError):
                    discovery.step()
            with database.connect_database() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM discovery_queue").fetchone()[0],1)
            response.status_code = 404
            with patch.object(discovery,"etsy_get",side_effect=HTTPError(response=response)):
                self.assertEqual(discovery.step(),"Skipped unavailable shop 1")
            with database.connect_database() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM discovery_queue").fetchone()[0],0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM discovery_checked").fetchone()[0],1)
