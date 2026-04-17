"""Backup TradingBonusHub SQL Server database.

Uses native SQL Server BACKUP DATABASE command — safe while the app is running.
Keeps the latest 7 backups, automatically deletes older ones.

Run manually:
    python scripts/backup_db.py

Or let Task Scheduler run it daily (see scripts/setup_backup_task.ps1).
"""
import os
import sys
from datetime import datetime
from pathlib import Path

import pyodbc
from dotenv import load_dotenv

# ── Configuration ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

DB_SERVER = os.environ.get("DB_SERVER", "localhost")
DB_NAME = os.environ.get("DB_NAME", "TradingBonusHub")
DB_USER = os.environ.get("DB_USER", "")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
BACKUP_DIR = ROOT / "data" / "backups"
KEEP_LAST = 7  # Number of backups to keep


def _conn_str() -> str:
    return (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE=master;"
        f"UID={DB_USER};"
        f"PWD={DB_PASSWORD};"
        f"TrustServerCertificate=yes;"
    )


def backup():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"{DB_NAME}_{timestamp}.bak"

    print(f"[INFO] Backing up {DB_NAME} on {DB_SERVER} ...")

    try:
        conn = pyodbc.connect(_conn_str(), autocommit=True)
        cursor = conn.cursor()

        # Full backup with compression (if supported by edition)
        backup_sql = f"""
            BACKUP DATABASE [{DB_NAME}]
            TO DISK = ?
            WITH FORMAT, INIT,
                 NAME = ?,
                 SKIP, NOREWIND, NOUNLOAD
        """
        backup_name = f"{DB_NAME} Full Backup {timestamp}"
        cursor.execute(backup_sql, (str(dest), backup_name))

        # SQL Server BACKUP may return multiple result sets — consume all
        while cursor.nextset():
            pass

        cursor.close()
        conn.close()

    except pyodbc.Error as e:
        print(f"[ERROR] Backup failed: {e}")
        sys.exit(1)

    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"[OK] Backup: {dest.name} ({size_mb:.1f} MB)")

    # Delete backups older than KEEP_LAST
    backups = sorted(BACKUP_DIR.glob(f"{DB_NAME}_*.bak"))
    if len(backups) > KEEP_LAST:
        for old in backups[:-KEEP_LAST]:
            old.unlink()
            print(f"[DEL] Removed old backup: {old.name}")

    print(f"[INFO] Backups kept: {min(len(backups), KEEP_LAST)}/{KEEP_LAST}")


if __name__ == "__main__":
    backup()
