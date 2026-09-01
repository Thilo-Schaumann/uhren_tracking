"""Runs all scrapers once and updates watches.db. Intended for a daily cron run."""
import sys

from db import connect, mark_missing_as_sold, today_str, upsert_listing
from scrapers import cologne_watch, grimmeissen, rothfuss

SCRAPERS = {
    "grimmeissen": grimmeissen.scrape,
    "rothfuss": rothfuss.scrape,
    "cologne_watch": cologne_watch.scrape,
}


def main():
    conn = connect()
    today = today_str()

    for platform, scrape_fn in SCRAPERS.items():
        try:
            items = scrape_fn()
        except Exception as exc:
            print(f"[{platform}] scrape failed: {exc}", file=sys.stderr)
            continue

        seen_ids = {item["external_id"] for item in items}
        for item in items:
            upsert_listing(conn, item, today)
        mark_missing_as_sold(conn, platform, seen_ids, today)
        conn.commit()
        print(f"[{platform}] {len(items)} active listings")

    conn.close()


if __name__ == "__main__":
    main()
