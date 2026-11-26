"""Offline daily backup; run with the vault key in the private environment."""
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os
import re
import stat
from favourite_feed.health_vault import DEFAULT_PATH, encrypted_backup, verify_backup

def private(path, directory=False):
    info = path.lstat()
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or (not directory and info.st_nlink != 1):
        raise RuntimeError("Unsafe private file or directory")

def rotate(vault, folder, now=None):
    now = now or datetime.now(timezone.utc)
    vault, folder = Path(vault).expanduser(), Path(folder).expanduser()
    private(vault.parent, True)
    private(vault)
    if folder.parent.resolve() != vault.parent.resolve():
        raise RuntimeError("Backup directory must be inside the private vault directory")
    folder.mkdir(mode=0o700, exist_ok=True)
    private(folder, True)
    target = folder / ("health-" + now.strftime("%Y-%m-%d") + ".enc")
    if not target.exists():
        encrypted_backup(target, vault)
    private(target)
    verify_backup(target)
    cutoff = now.date() - timedelta(days=6)
    for item in folder.iterdir():
        if not re.fullmatch(r"health-\d{4}-\d{2}-\d{2}\.enc", item.name):
            continue
        day = datetime.strptime(item.name[7:-4], "%Y-%m-%d").date()
        if day < cutoff:
            private(item)
            item.unlink()
    return target

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    rotate(args.vault, args.vault.parent / "backups")
    print("Daily encrypted backup verified; expired daily copies pruned.")
