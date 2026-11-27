import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from favourite_feed import database, refresh_jobs


class RefreshJobTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = patch.object(database, "DB_PATH", Path(tmp.name) / "test.db")
        p.start()
        self.addCleanup(p.stop)
        database.setup_database()
        with database.connect_database() as conn:
            conn.execute("""INSERT INTO monitored_shops
                (shop_id,shop_name,shop_url,added_at)
                VALUES (1,'Example','https://www.etsy.com/shop/Example','2026-01-01')""")

    def test_idle_and_paused_step(self):
        self.assertEqual(refresh_jobs.step()["status"], "never")
        refresh_jobs.start()
        refresh_jobs.pause()
        self.assertEqual(refresh_jobs.step()["status"], "paused")

    def test_rate_limit_preserves_partial_counts(self):
        def partial(shop):
            with database.connect_database() as conn:
                conn.execute("""INSERT INTO listings
                    (listing_id,shop_id,title,published_at,discovered_at)
                    VALUES (10,1,'Example',1,'2026-01-01')""")
            raise RuntimeError("Etsy API rate limit reached")

        refresh_jobs.start()
        with patch.object(refresh_jobs, "refresh_shop", side_effect=partial):
            result = refresh_jobs.step()
        self.assertEqual((result["status"], result["done"], result["new_listings"]), ("paused",0,1))
        self.assertIsNone(refresh_jobs.start()["error"])
        with patch.object(refresh_jobs, "refresh_shop", return_value="Finished"):
            result = refresh_jobs.step()
        self.assertEqual((result["status"], result["done"], result["new_listings"]), ("completed",1,1))
        with database.connect_database() as conn:
            self.assertEqual(conn.execute("SELECT new_listings FROM refresh_run_shops").fetchone()[0],1)

    def test_paused_shop_is_skipped(self):
        refresh_jobs.start()
        with database.connect_database() as conn:
            conn.execute("UPDATE monitored_shops SET is_active=0")
        with patch.object(refresh_jobs, "refresh_shop") as refresh:
            result = refresh_jobs.step()
        refresh.assert_not_called()
        self.assertEqual((result["status"],result["done"],result["baselines"]),("completed",1,0))
