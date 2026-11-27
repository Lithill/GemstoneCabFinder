# Personal dashboard

A Flask dashboard for Etsy gemstone collecting and identification practice, a private health diary, and houseplant care.

## Application layout

- `favourite_feed/web.py`: Flask entry point and route registration.
- `feed_routes.py`, `seller_routes.py`, `refresh_routes.py`, `quiz_routes.py` within `favourite_feed/`: gemstone dashboard sections.
- `favourite_feed/health_*.py`: private health diary, encrypted storage and analysis.
- `favourite_feed/plants.py`: houseplant diary.
- `favourite_feed/database.py`: gemstone database connection and schema helpers.
- `favourite_feed/templates/` and `favourite_feed/static/`: browser interface.
- `tests/`: offline regression tests using fictional data.
- `docs/gemstone-workflow.md`: routine gemstone workflow.

## Development and deployment

Install application dependencies in an appropriate virtual environment with `python -m pip install -r requirements.txt`. Legacy spreadsheet tools have separate dependencies in `requirements-legacy.txt`.

GitHub Actions runs the offline regression suite on pushes to main. Check the latest workflow result before deploying. Run the full suite on a development machine when needed:

    python -m unittest discover -s tests -v

On CPU-limited PythonAnywhere, avoid repeating the full suite for every small change. Once the intended batch has passed CI, pull it:

    cd ~/GemstoneCabFinder
    git pull --ff-only origin main

Reload the web app in the PythonAnywhere Web tab and check the affected pages. Keep the existing WSGI configuration and private environment settings.

## Data and security

The gemstone, plant and encrypted health databases remain separate. Do not commit databases, credentials, private configuration or encryption keys. Preserve existing database files during upgrades. The health diary requires HTTPS and upstream site authentication in the configured personal deployment; do not expose it publicly. Keep the private vault key and recoverable encrypted backups safe. Same-host backups alone do not protect against host loss.

## Legacy tools

The original desktop spreadsheet workflow remains available for historical compatibility. Routine seller discovery and review now take place in the dashboard. Do not run legacy imports or searches against existing data without checking their paths and intended effects.
