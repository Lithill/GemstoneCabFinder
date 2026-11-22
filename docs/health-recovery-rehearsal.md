# Health vault recovery rehearsal and release gate

The repeatable synthetic recovery drill is `python scripts/rehearse_health_recovery.py`. It is also run by the health security GitHub Actions workflow on the development branch. It creates a new random key, a new private vault and fictional answers inside a disposable temporary directory. It does **not** read, inspect, modify or restore any existing user vault, production database or PythonAnywhere files.

The drill checks the complete path: save a fictional check-in; create an encrypted backup; authenticate every backed-up record; simulate loss of the working database; restore into a **new** destination; compare the recovered answers; edit a recovered entry; reject a wrong-key restore; and refuse overwriting an existing restored database. Notes are excluded, and the encrypted backup is checked for obvious plaintext markers. A passing drill is evidence of recovery functionality, **not** a substitute for independent security review.

## Production recovery still needs decisions and approval

Before enabling real symptom storage, establish a private backup location, backup frequency, retention period, key recovery method, permission checks, and a documented procedure to test a restore without overwriting the working vault. An encrypted backup is only recoverable while the correct encryption key is retained. Do not put the key or health records in GitHub, app logs, screenshots or the gemstone database. Existing backup copies can still contain deleted entries; deletion in the active vault does not erase historical backups or filesystem snapshots.

**Current state:** No live health-data storage approval. The staging API remains behind two explicit feature switches, and no deployment or database migration is authorized. The recovery drill uses fictional data only. Next release gate is a focused review of web authentication/CSRF, private file permissions, error handling, user consent and retention/deletion policy, followed by a user-approved deployment plan.
