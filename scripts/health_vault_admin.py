"""Manual health-vault administration. Not exposed by the web server."""
import argparse
from getpass import getpass
from pathlib import Path
from cryptography.fernet import Fernet
from favourite_feed.health_vault import password_hash, provision, encrypted_backup, restore_backup, verify_backup

# Manual administration commands for creating credentials, provisioning storage and managing backups.
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["new-key", "password-hash", "provision", "backup", "restore", "verify-backup"])
    parser.add_argument("path", nargs="?")
    parser.add_argument("destination", nargs="?")
    args = parser.parse_args()
    # Generate a new random encryption key. Keep the printed value private and preserve the original key for existing vaults.
    if args.action == "new-key":
        print("HEALTH_VAULT_KEY=" + Fernet.generate_key().decode())
    # Read the separate tracker password without displaying typed characters and confirm it before hashing.
    elif args.action == "password-hash":
        first = getpass("New tracker password (16+ characters): ")
        if first != getpass("Confirm tracker password: "):
            raise SystemExit("Passwords do not match.")
        print("HEALTH_PASSWORD_HASH=" + password_hash(first))
    # Create an empty vault at the supplied or default path; provisioning refuses to overwrite existing files.
    elif args.action == "provision":
        provision(Path(args.path).expanduser() if args.path else None) if args.path else provision()
        print("Empty encrypted-record vault provisioned. No tracker data collection enabled.")
    # Write an encrypted snapshot of the default vault to a new destination.
    elif args.action == "backup":
        if not args.path:
            parser.error("backup requires a destination path")
        encrypted_backup(Path(args.path))
        print("Encrypted backup written.")
    # Authenticate the backup and check database integrity without printing diary answers.
    elif args.action == "verify-backup":
        if not args.path:
            parser.error("verify-backup requires a backup path")
        count = verify_backup(Path(args.path))
        print(f"Encrypted backup authenticated; SQLite integrity OK; {count} encrypted entries.")
    # Restore to a new database destination only; the vault helper verifies the key and refuses overwrites.
    else:
        if not args.path or not args.destination:
            parser.error("restore requires backup path and new database destination")
        restore_backup(Path(args.path), Path(args.destination))
        print("Restored to new database path.")

if __name__ == "__main__":
    main()
