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
    reference_number TEXT,
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
"""


def connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def upsert_listing(conn: sqlite3.Connection, item: dict, today: str) -> int:
    """Insert or update a listing seen today, and record its price snapshot."""
    row = conn.execute(
        "SELECT id FROM listings WHERE platform = ? AND external_id = ?",
        (item["platform"], item["external_id"]),
    ).fetchone()

    if row is None:
        cur = conn.execute(
            """INSERT INTO listings
               (platform, external_id, seller, brand, model, reference_number,
                url, first_seen, last_seen, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
            (
                item["platform"], item["external_id"], item["seller"],
                item.get("brand"), item.get("model"), item.get("reference_number"),
                item["url"], today, today,
            ),
        )
        listing_id = cur.lastrowid
    else:
        listing_id = row[0]
        conn.execute(
            "UPDATE listings SET last_seen = ?, status = 'active' WHERE id = ?",
            (today, listing_id),
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


def today_str() -> str:
    return date.today().isoformat()
