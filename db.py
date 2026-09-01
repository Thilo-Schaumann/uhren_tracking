"""SQLite schema and upsert logic for the watch tracker."""
import sqlite3
from datetime import date

DB_PATH = "watches.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    external_id TEXT NOT NULL,
    seller TEXT NOT NULL,
    brand TEXT,
    model TEXT,
    model_line TEXT,
    reference_number TEXT,
    condition TEXT,
    year TEXT,
    has_papers INTEGER,
    has_box INTEGER,
    band_material TEXT,
    dial_color TEXT,
    image_url TEXT,
    url TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    UNIQUE(platform, external_id)
);

CREATE TABLE IF NOT EXISTS price_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL REFERENCES listings(id),
    date TEXT NOT NULL,
    price REAL,
    currency TEXT NOT NULL DEFAULT 'EUR',
    UNIQUE(listing_id, date)
);

CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand TEXT NOT NULL,
    model_line TEXT NOT NULL,
    reference_number TEXT NOT NULL,
    display_name TEXT,
    image_url TEXT,
    added_at TEXT NOT NULL,
    UNIQUE(brand, model_line, reference_number)
);
"""

# Columns added after the initial release; applied to pre-existing databases via ALTER TABLE.
LISTING_COLUMNS_V2 = [
    ("model_line", "TEXT"),
    ("condition", "TEXT"),
    ("year", "TEXT"),
    ("has_papers", "INTEGER"),
    ("has_box", "INTEGER"),
    ("band_material", "TEXT"),
    ("dial_color", "TEXT"),
    ("image_url", "TEXT"),
]


def _migrate(conn: sqlite3.Connection):
    existing = {row[1] for row in conn.execute("PRAGMA table_info(listings)")}
    for name, sqltype in LISTING_COLUMNS_V2:
        if name not in existing:
            conn.execute(f"ALTER TABLE listings ADD COLUMN {name} {sqltype}")


def connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def upsert_listing(conn: sqlite3.Connection, item: dict, today: str) -> int:
    """Insert or update a listing seen today, and record its price snapshot."""
    row = conn.execute(
        "SELECT id FROM listings WHERE platform = ? AND external_id = ?",
        (item["platform"], item["external_id"]),
    ).fetchone()

    spec_fields = (
        item.get("brand"), item.get("model"), item.get("model_line"),
        item.get("reference_number"), item.get("condition"), item.get("year"),
        item.get("has_papers"), item.get("has_box"), item.get("band_material"),
        item.get("dial_color"), item.get("image_url"),
    )

    if row is None:
        cur = conn.execute(
            """INSERT INTO listings
               (platform, external_id, seller, brand, model, model_line, reference_number,
                condition, year, has_papers, has_box, band_material, dial_color, image_url,
                url, first_seen, last_seen, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
            (item["platform"], item["external_id"], item["seller"], *spec_fields,
             item["url"], today, today),
        )
        listing_id = cur.lastrowid
    else:
        listing_id = row[0]
        conn.execute(
            """UPDATE listings SET last_seen = ?, status = 'active',
               brand = ?, model = ?, model_line = ?, reference_number = ?,
               condition = ?, year = ?, has_papers = ?, has_box = ?,
               band_material = ?, dial_color = ?, image_url = ?
               WHERE id = ?""",
            (today, *spec_fields, listing_id),
        )

    if item.get("price") is not None:
        conn.execute(
            """INSERT OR REPLACE INTO price_snapshots (listing_id, date, price, currency)
               VALUES (?, ?, ?, ?)""",
            (listing_id, today, item["price"], item.get("currency", "EUR")),
        )

    return listing_id


def mark_missing_as_sold(conn: sqlite3.Connection, platform: str, seen_external_ids: set, today: str):
    """Any active listing for this platform not seen in today's scrape is considered sold."""
    rows = conn.execute(
        "SELECT id, external_id FROM listings WHERE platform = ? AND status = 'active'",
        (platform,),
    ).fetchall()
    for listing_id, external_id in rows:
        if external_id not in seen_external_ids:
            conn.execute(
                "UPDATE listings SET status = 'sold' WHERE id = ?",
                (listing_id,),
            )


def add_favorite(conn: sqlite3.Connection, brand: str, model_line: str, reference_number: str,
                  display_name: str = None, image_url: str = None):
    conn.execute(
        """INSERT OR IGNORE INTO favorites (brand, model_line, reference_number, display_name, image_url, added_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (brand, model_line, reference_number, display_name, image_url, today_str()),
    )


def list_favorites(conn: sqlite3.Connection):
    return conn.execute("SELECT * FROM favorites").fetchall()


def today_str() -> str:
    return date.today().isoformat()
