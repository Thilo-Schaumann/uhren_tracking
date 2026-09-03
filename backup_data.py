"""Weekly safety-net backup: copies all collected data into backup/, overwriting
the previous copy each run. Independent of git — a plain filesystem copy of
whatever is currently on disk."""
import shutil
from datetime import datetime
from pathlib import Path

FILES_TO_BACKUP = [
    "watches.db",
    "model_variants.json",
    "brand_logos.json",
    "official_prices.json",
]

BACKUP_DIR = Path("backup")


def run():
    BACKUP_DIR.mkdir(exist_ok=True)
    copied = []
    for name in FILES_TO_BACKUP:
        src = Path(name)
        if src.exists():
            shutil.copy2(src, BACKUP_DIR / name)
            copied.append(name)
    (BACKUP_DIR / "last_backup.txt").write_text(datetime.now().isoformat())
    print(f"Backed up {len(copied)} files to {BACKUP_DIR}/: {', '.join(copied)}")


if __name__ == "__main__":
    run()
