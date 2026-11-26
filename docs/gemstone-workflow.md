# Gemstone dashboard workflow

The dashboard is the primary workflow. The old desktop Excel workflow is retired for normal use; retain its scripts and files for historical recovery until a separate removal audit.

## Everyday use
- Discover gemstone sellers (/discover): edit search terms, start a search, continue it in the browser, pause or resume. Review pending shops by opening the full Etsy storefront. Reject or add to favourites.
- Manage favourite shops (/favourite-shops): add manually, pause/resume monitoring, or import 5, 10 or 20 recent listings.
- Refresh shops: run the resumable refresh to collect newly published listings. The feed preserves seen and liked state.
- Gemstone quiz and library: existing learning and corrections are retained.

## Storage
The live gemstone database is data/favourite_feed.db (ignored by Git). Back it up using SQLite's backup API before upgrades. Do not overwrite it with a desktop database. Keep backups private.
The old spreadsheet and gemstone_sellers.db are not the dashboard's source of truth.
The one-off command python -m favourite_feed.import_review_list imports the 80 supplied spreadsheet rows without overwriting existing decisions or monitored shops. It is safe to repeat.
Legacy reviewed_shop_ids.txt contains previously discovered IDs, not a reliable list of rejected shops; pending dashboard rows take precedence. Keep this file and favourited_shops.txt for discovery exclusions.

## Legacy commands
Do not use main.py, import_saved_shops.py, import_favourites.py or setup_database.py for routine dashboard updates. These are retained for historical recovery and may use different paths/databases. Do not remove config.py: discovery still imports it.

## Deployment checks
From the project directory, git pull --ff-only origin main, then python -m unittest discover -s tests -v. Reload the PythonAnywhere web app only after tests pass. Verify discovery, favourite shop management, feed refresh and quiz on the live site.
Search and refresh are browser-driven; they do not run continuously in the background. Etsy rate limits and network failures can interrupt them.
