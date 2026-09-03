"""Weekly safety-net backup: copies all collected data into backup/, overwriting
the previous copy each run. Independent of git — a plain filesystem copy of
whatever is currently on disk. Also dumps every watches.db table as CSV so it
can be opened without a SQLite viewer."""
import csv
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

FILES_TO_BACKUP = [
    "watches.db",
    "model_variants.json",
    "brand_logos.json",
    "official_prices.json",
]

BACKUP_DIR = DATA_DIR / "backup"


def _export_csv_tables():
    conn = sqlite3.connect(DATA_DIR / "watches.db")
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )]
    for table in tables:
        cursor = conn.execute(f"SELECT * FROM {table}")
        columns = [d[0] for d in cursor.description]
        with open(BACKUP_DIR / f"{table}.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(cursor)
    conn.close()
    return tables


def run():
    BACKUP_DIR.mkdir(exist_ok=True)
    copied = []
    for name in FILES_TO_BACKUP:
        src = DATA_DIR / name
        if src.exists():
            shutil.copy2(src, BACKUP_DIR / name)
            copied.append(name)
    tables = _export_csv_tables()
    (BACKUP_DIR / "last_backup.txt").write_text(datetime.now().isoformat())
    print(f"Backed up {len(copied)} files to {BACKUP_DIR}/: {', '.join(copied)}")
    print(f"Exported {len(tables)} tables as CSV: {', '.join(t + '.csv' for t in tables)}")


if __name__ == "__main__":
    run()
