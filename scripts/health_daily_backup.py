"""Offline daily backup; run with the vault key in the private environment."""
import argparse
import tempfile
import fcntl
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os
import re
import stat
from favourite_feed.health_vault import DEFAULT_PATH, encrypted_backup, verify_backup

# Inspect the file itself rather than following symbolic links; require current-user ownership, private permissions and no extra hard links for files.
def private(path, directory=False):
    info = path.lstat()
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or (not directory and info.st_nlink != 1):
        raise RuntimeError("Unsafe private file or directory")

# Check the vault and backup directory before starting a rotation, using UTC by default.
def rotate(vault, folder, now=None, refresh=False):
    now = now or datetime.now(timezone.utc)
    vault, folder = Path(vault).expanduser(), Path(folder).expanduser()
    private(vault.parent, True)
    private(vault)
    # Keep backups in a sibling directory under the same private parent; these are local backups, not off-site copies.
    if folder.parent.resolve() != vault.parent.resolve():
        raise RuntimeError("Backup directory must be inside the private vault directory")
    folder.mkdir(mode=0o700, exist_ok=True)
    private(folder, True)
    # Use an exclusive filesystem lock to prevent overlapping rotations from changing the same backup simultaneously.
    lock = folder / '.rotation.lock'
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'rb') as handle:
        private(lock)
        fcntl.flock(handle, fcntl.LOCK_EX)
        return _rotate_locked(vault, folder, now, refresh)


# Perform the rotation while holding the lock; use one dated filename per day.
def _rotate_locked(vault, folder, now, refresh):
    target = folder / ("health-" + now.strftime("%Y-%m-%d") + ".enc")
    if target.exists():
        private(target)
    # Create and verify a temporary replacement before atomically replacing today's existing backup.
    if refresh:
        with tempfile.TemporaryDirectory(dir=folder) as tmp:
            candidate = Path(tmp) / 'snapshot.enc'
            encrypted_backup(candidate, vault)
            private(candidate)
            verify_backup(candidate)
            os.replace(candidate, target)
    # Without refresh, create today's backup only if it does not already exist.
    elif not target.exists():
        encrypted_backup(target, vault)
    private(target)
    verify_backup(target)
    # Retain today's date and the preceding six calendar dates; pruning happens only when rotation runs.
    cutoff = now.date() - timedelta(days=6)
    for item in folder.iterdir():
        # Ignore unrelated filenames so rotation does not delete arbitrary files.
        if not re.fullmatch(r"health-\d{4}-\d{2}-\d{2}\.enc", item.name):
            continue
        day = datetime.strptime(item.name[7:-4], "%Y-%m-%d").date()
        if day < cutoff:
            private(item)
            # Remove only an expired matching backup that has passed the private-file check.
            item.unlink()
    return target

# Manual command-line entry point; the web API instead supplies its own backup folder and refresh option.
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    rotate(args.vault, args.vault.parent / "backups")
    print("Daily encrypted backup verified; expired daily copies pruned.")
