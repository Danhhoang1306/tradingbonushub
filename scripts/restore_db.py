"""Restore TradingBonusHub SQL Server database from a .bak file.

Usage:
    python scripts/restore_db.py                    # restores the latest backup
    python scripts/restore_db.py <backup_name.bak>  # restores a specific file

WARNING: This overwrites the live database. Stop the app (stop.bat) first.
"""
import os
import sys
from pathlib import Path

import pyodbc
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

DB_SERVER = os.environ.get("DB_SERVER", "localhost")
DB_NAME = os.environ.get("DB_NAME", "TradingBonusHub")
DB_USER = os.environ.get("DB_USER", "")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
BACKUP_DIR = ROOT / "data" / "backups"


def _conn_str() -> str:
    return (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE=master;"
        f"UID={DB_USER};"
        f"PWD={DB_PASSWORD};"
        f"TrustServerCertificate=yes;"
    )


def _pick_backup(arg: str | None) -> Path:
    if arg:
        p = Path(arg)
        if not p.is_absolute():
            p = BACKUP_DIR / p
        if not p.exists():
            print(f"[ERROR] Backup not found: {p}")
            sys.exit(1)
        return p

    backups = sorted(BACKUP_DIR.glob(f"{DB_NAME}_*.bak"))
    if not backups:
        print(f"[ERROR] No backups in {BACKUP_DIR}")
        sys.exit(1)
    return backups[-1]


def restore(src: Path):
    print(f"[INFO] Restoring {DB_NAME} from {src.name} ...")
    print(f"[WARN] This will overwrite the current database.")
    confirm = input("Type 'YES' to continue: ").strip()
    if confirm != "YES":
        print("[INFO] Aborted.")
        sys.exit(0)

    try:
        conn = pyodbc.connect(_conn_str(), autocommit=True)
        cursor = conn.cursor()

        # Kick everyone out so RESTORE can take an exclusive lock.
        cursor.execute(f"ALTER DATABASE [{DB_NAME}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
        while cursor.nextset():
            pass

        cursor.execute(
            f"RESTORE DATABASE [{DB_NAME}] FROM DISK = ? WITH REPLACE, RECOVERY",
            (str(src),),
        )
        while cursor.nextset():
            pass

        cursor.execute(f"ALTER DATABASE [{DB_NAME}] SET MULTI_USER")
        while cursor.nextset():
            pass

        cursor.close()
        conn.close()

    except pyodbc.Error as e:
        print(f"[ERROR] Restore failed: {e}")
        sys.exit(1)

    print(f"[OK] Restored {DB_NAME} from {src.name}")
    print(f"[INFO] You can now start the app (start.bat).")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    restore(_pick_backup(arg))
