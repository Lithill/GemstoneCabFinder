# Health tracker: security staging (NOT LIVE)

This branch contains an **offline-only** encrypted SQLite vault foundation and an isolated health login blueprint that is **not registered with the Flask app**.
The existing `/symptom-tracker` remains a non-saving prototype. No health API,
login, cookies, health-data writes or data migration have been enabled.

## Secrets and setup (manual, later)

- Install `cryptography` in the PythonAnywhere virtual environment.
- Run `python3.12 -m scripts.health_vault_admin new-key` to generate a Fernet key.
- Run `python3.12 -m scripts.health_vault_admin password-hash` to create a scrypt password verifier.
- Keep `HEALTH_VAULT_KEY` and `HEALTH_PASSWORD_HASH` only in private server environment variables, never in GitHub, logs, or browser code. Use a distinct Flask session signing secret.
- Run `python3.12 -m scripts.health_vault_admin provision` only after configuring the key. The database defaults to `~/.gemstonecabfinder-private/health_vault.db` (outside the repository). Parent permissions 0700, DB 0600.
- An entry is uniquely keyed by ISO date + question, so an update replaces that day's answer.
- To create an encrypted snapshot: `python3.12 -m scripts.health_vault_admin backup ~/private-backups/health-YYYY-MM-DD.backup`. Backups use the same vault key: protect the key separately. Verify restoration with `restore BACKUP NEW_DB_PATH`, then test the restored records using the key. Store a copy off-host. Do not commit backups.

## Must complete before health data collection

1. Review and test the staged, **unregistered** `health_auth` blueprint: strong password verifier, secure signed session cookie with 20-minute expiry, login CSRF token, and persistent per-address login throttling. Add a usable logout form, session invalidation/rotation strategy, stronger abuse protection, and automated login/logout/security tests before registering any routes. Never reuse the gemstone site's weak shared password.
2. Ensure all read/write routes require authentication, use no-store caching and a restrictive CSP, and never log answers. Disable browser caching of sensitive pages.
3. Test server-side per-day upsert and prefilled guided/quick check-ins, including timezone/date boundaries and period skip behavior.
4. Test encrypted backup, off-host copy, recovery, and restore drills; agree on backup cadence and retention. Keep secrets out of backups and version control.
5. Assess free-hosting storage, backups, operational constraints, and the risks of storing sensitive health information on a shared free hosting tier. Confirm the user is comfortable with the risks before turning on collection.

**Important:** Fernet encrypts individual record payloads at rest, but SQLite
metadata (dates, question names, update timestamps) remains plaintext.
The database file itself is not fully encrypted. This distinction matters
for health information; consider encrypting metadata or full-database encryption
before production use. Encrypted backups encrypt the complete snapshot.

## Automated offline checks

The development branch includes `tests/test_health_auth.py`, `tests/test_health_vault.py`, and `.github/workflows/health-security-tests.yml`. The workflow runs on pushes to `feature/favourite-feed` using free GitHub-hosted runner capacity subject to the repository's Actions allowance. Check the actual workflow result before treating tests as passed; the presence of test code alone is not verification. The tests use only synthetic values and temporary databases, never production health data.

## Vault schema privacy revision

The offline vault now stores only a keyed HMAC entry identifier and Fernet-encrypted JSON containing date, symptom name, and answer. This prevents readable symptom names and dates in the SQLite file. The revision changes the schema and is **not compatible with previously provisioned prototype health vault files**. No live health-data collection has been enabled. Do not attempt to overwrite any existing vault; if a test vault already exists, preserve it and plan an explicit offline migration before use. Test the new schema and backup/restore before any activation.

## Disabled-by-default private tracker preview

The existing public `/symptom-tracker` remains a temporary, non-saving
prototype. The Flask application now registers `/health-auth/*` and
`/private-symptom-tracker` **only** when
`HEALTH_TRACKER_PREVIEW_ENABLED=1` is explicitly set. By default, these
routes are absent and the health cryptography module is not imported by
`web.py`, preserving the existing live installation.

Do **not** set this flag on PythonAnywhere yet. Enabling the preview requires
installing the tested cryptography dependency, configuring the separate
password hash, vault key and session secret outside GitHub, checking HTTPS
proxy behaviour, and completing a deployment security review. The preview
still has no health-data saving endpoint, even if the flag is enabled.

## Offline deletion and retention

The offline vault now supports `delete(day, question)` for a single encrypted
entry, with regression tests for exact-match deletion and incorrect-key
rejection. No deletion or saving endpoint is exposed to the browser.

**Important:** deleting a SQLite row is *logical deletion*, not guaranteed
secure erasure of every byte on disk. SQLite free pages, journal/WAL files,
filesystem snapshots and previously created encrypted backups may still
contain old ciphertext. A future live release needs a documented retention,
backup expiration, deletion and account-erasure policy before accepting
personal health information. Never claim that deleting a row erases every
historical copy.

## Offline recovery drill

The automated vault tests exercise a complete backup, authentication and
integrity verification, restore to a **new** database, and independent reading
of multiple encrypted answers. They also check that deleting an entry from
the restored copy does not alter the original vault or its encrypted backup.

For an offline manual check, with `HEALTH_VAULT_KEY` configured outside Git:

```sh
python scripts/health_vault_admin.py backup /private/path/backup.enc
python scripts/health_vault_admin.py verify-backup /private/path/backup.enc
python scripts/health_vault_admin.py restore /private/path/backup.enc /private/path/restored.db
```

Use new paths, never overwrite the production gemstone database or an
existing health vault. These commands do not activate web collection.
A passing automated recovery drill is not a substitute for testing a real
deployment's backup permissions, off-host backup custody, and restoration
procedure before enabling health-data storage.
