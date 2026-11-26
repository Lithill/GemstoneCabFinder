# Health tracker security and privacy review — 2026-11-22

**Decision: NOT READY FOR REAL HEALTH DATA / NO DEPLOYMENT APPROVAL.**

Scope: code review of `health_auth.py`, `health_api.py`, `health_staging.py`, `health_vault.py`, `health_diary_bridge.py`, `health_checkins.py`, the staging browser client, and synthetic recovery rehearsal. This is an internal implementation review, **not** an independent penetration test or a completed privacy assessment.

## Findings and actions

1. **High — production vault confusion / insufficient emergency off switch.** A configured staging API previously remained callable after the storage environment switch was removed (until process restart), and its path restriction only rejected `favourite_feed.db`. Fixed: every request checks the storage switch, and staging rejects the reserved production health vault name, the gemstone database name, and symlink paths. Regression tests added. **Residual:** deployment configuration must be reviewed for path aliases and filesystem permissions.
2. **Medium — signed but malformed session could produce HTTP 500.** A correctly signed JSON list or string caused `data.get` to fail. Fixed by requiring a dict before accessing fields; regression test added.
3. **Low — rate-limit SQLite connection leaked on initialization failure.** Fixed by closing on setup errors.
4. **High — deletion semantics and backup retention remain unresolved.** Deleting an entry removes its active logical row, **not** historical encrypted backups, SQLite freed pages, storage-provider snapshots or log copies. Do not promise permanent deletion. The UI now warns that old backups can retain an entry, but a retention/deletion policy and technical enforcement are still required.
5. **High — backup operations are manual only.** Synthetic create/verify/restore tests pass, but there is no production backup schedule, encrypted off-host copy, monitoring or key-recovery process. Do not enable saving until a recovery procedure is approved and tested on the target host.
6. **Medium — privacy and access controls need host verification.** Confirm vault directory 0700, file 0600, SQLite journal/WAL/SHM permissions, HTTPS, no secret leakage in logs, no caching of health responses, cookie flags and session expiry. Verify backups cannot be served by Flask or the web server. The staging browser retains answers in memory until the page is closed; explicit logout does not currently clear the already-open page's in-memory diary.
7. **Medium — browser workflow limitations.** Save updates only supplied questions, so a removed on-screen answer is **not** deleted from storage; deletion requires the separate confirmation action. No autosave is intentional. Date switching can leave an on-screen diary from a different date; the user must load a date before editing. A clearer dirty-state indicator and a current-day binding are required before live use.
8. **Medium — server hardening outstanding.** Add strict request Origin checks and targeted rate limits for write operations, improve error handling for missing/corrupted vaults without leaking internals, and validate filesystem ownership and path isolation against hard links/aliases. Browser end-to-end testing and an independent security review remain outstanding.

## Proposed retention policy for user decision (not implemented)

- **Active check-ins:** retain until the user explicitly deletes them or requests complete removal; avoid automatic deletion until requirements are agreed.
- **Encrypted backups:** propose at most **7 daily rolling copies**, deleted after **7 days**; do not assume this is adequate for recovery or privacy without user approval. Retention enforcement and backup verification need to be implemented.
- **Deleted entries:** warn that they may persist in retained backups until those backups expire; immediate erasure requires a separate process that rebuilds the encrypted vault and safely replaces/retires older backups, with host-level limitations documented.
- **Encryption key:** never store in GitHub, database, logs or a publicly accessible directory. Document how the user can recover it without leaving an unencrypted copy in an unsafe place.
- **Optional free-text notes:** continue excluding them from transmitted and stored answers until specifically approved.

## Release blockers

- [ ] User agrees to a clear backup retention and deletion policy.
- [ ] Implement and verify private backup scheduling, pruning, recovery key handling and host permission checks.
- [ ] Fix remaining browser workflow and write-endpoint safeguards above.
- [ ] Complete browser-based acceptance testing with fictional data, security review and a recovery rehearsal on a separate private test vault.
- [ ] Prepare deployment rollback plan that cannot modify `data/favourite_feed.db`.
- [ ] Obtain **explicit user approval** before enabling any real health-data saving.

**Operational status:** no deployment, no merge to main, no production vault provisioning, no health-data collection. Work remains on `feature/favourite-feed`.
