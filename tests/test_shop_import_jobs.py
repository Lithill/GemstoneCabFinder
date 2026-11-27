import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from favourite_feed import database, shop_import_jobs as jobs
from favourite_feed.shop_management import add_shop


class ShopImportJobsTests(unittest.TestCase):
    def test_resume_and_skip_existing(self):
        with TemporaryDirectory() as tmp, patch.object(database,"DB_PATH",Path(tmp)/"test.db"):
            database.setup_database()
            with patch("favourite_feed.shop_management.find_shop_by_name",return_value={"shop_id":123,"shop_name":"ExampleShop"}):
                add_shop("ExampleShop")
            rows = [{"listing_id":i,"title":"Example","creation_timestamp":100} for i in range(1,8)]
            with patch("favourite_feed.shop_import_jobs.etsy_get",return_value={"results":rows,"count":7}) as api, patch("favourite_feed.refresh.etsy_get",return_value={"results":[]}):
                jobs.start(123)
                self.assertEqual(jobs.step(123)["processed"],5)
                saved = jobs.list_jobs()[0]
                self.assertEqual((saved["shop_name"],saved["processed"],saved["done"]),("ExampleShop",5,0))
                jobs.start(123)
                self.assertEqual(jobs.status(123)["processed"],5)
                with patch("favourite_feed.shop_import_jobs.store_listing",side_effect=RuntimeError("temporary failure")):
                    with self.assertRaises(RuntimeError):
                        jobs.step(123)
                self.assertEqual(jobs.status(123)["processed"],5)
                result=jobs.step(123)
                self.assertEqual((result["done"],result["imported"],result["skipped"]),(1,7,0))
                self.assertEqual(api.call_count,1)
                self.assertEqual(jobs.list_jobs()[0]["done"],1)
                jobs.start(123)
                jobs.step(123)
                result=jobs.step(123)
                self.assertEqual((result["done"],result["imported"],result["skipped"]),(1,0,7))
