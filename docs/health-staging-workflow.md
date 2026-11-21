# Private symptom-tracker staging workflow

**Not approved for production health-data collection.** The public `/symptom-tracker` remains memory-only.

## What is implemented

The staging-only path is login -> private tracker -> explicit Save / Load -> encrypted offline vault -> edit or confirmed delete -> logout. Guided and quick entry share the existing in-memory diary. The browser strips notes before sending check-ins, and the server independently discards notes. Saving one day updates only the supplied questions; omitting an answer does **not** delete an older saved answer. Use the separate confirmed delete action for that.

The private API uses the existing signed session, same-origin Secure/HttpOnly cookie, session-bound CSRF token, bounded JSON request size, strict answer validation and a pre-provisioned encrypted vault. Failed validation and SQLite errors do not partially save a check-in. Session expiry requires signing in again. The prototype itself remains usable without any health API.

## Disabled-by-default gates

Both `HEALTH_TRACKER_PREVIEW_ENABLED=1` **and** `HEALTH_STAGING_STORAGE_ENABLED=1` must be explicitly configured before any web health-data API is registered. The second gate is deliberately absent from production configuration. `HEALTH_STAGING_VAULT_PATH` must point to an already-provisioned, isolated private vault; the API never provisions one. Login also requires `HEALTH_PASSWORD_HASH`, `HEALTH_SESSION_SECRET`, and `HEALTH_VAULT_KEY`.

**Do not set these flags on PythonAnywhere or deploy this workflow for real health information yet.** Run the synthetic integration tests through GitHub Actions only.

## Remaining security and product gates

- Independent end-to-end review of the authentication, CSRF, browser behaviour, request limits, vault permissions, backup/recovery and error handling.
- Clear retention policy, encrypted-backup lifecycle and explanation that SQLite deletion does not guarantee secure erasure of historical backups or filesystem snapshots.
- Dedicated private deployment configuration, safe backup/restore drill and rollback plan, with strict separation from `data/favourite_feed.db`.
- User review of what is stored, whether optional notes should remain excluded, and **explicit approval** before enabling real health-data saving.

Never merge the development branch into main without approval. Never alter or reset the existing gemstone database.
