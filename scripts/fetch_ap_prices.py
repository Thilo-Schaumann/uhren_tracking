"""Fetches official Audemars Piguet retail prices directly from audemarspiguet.com.

AP's own site exposes two undocumented JSON endpoints (found by inspecting network
traffic, not from any public API docs):
  - .../watch-collection/<any-slug>.products.core-collection.json
        -> the full current catalog (all lines), with full reference numbers
           like "15720ST.OO.A010CA.01" (case + bracelet/dial suffix)
  - .../home.price.<full-reference>.de.json
        -> {"price": {"amount": ..., "currency": "EUR", ...}}

Our scraped listings only carry the short case reference (e.g. "15720ST"),
since that's all the pre-owned shops publish. A short reference can match
several full references (different dial colors) at different prices, so a
price is only recorded when either exactly one full reference matches, or
all matches share the same price — never guessed.
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from db import connect

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; watch-price-tracker/1.0)"}
CATALOG_URL = "https://www.audemarspiguet.com/de/de/watch-collection/royal-oak.products.core-collection.json"
PRICE_URL = "https://www.audemarspiguet.com/de/de/home.price.{ref}.de.json"


def fetch_catalog_references() -> list[str]:
    req = urllib.request.Request(CATALOG_URL, headers=HEADERS)
    data = json.loads(urllib.request.urlopen(req, timeout=15).read())
    return [r["reference"] for r in data["results"]]


def fetch_price(full_ref: str) -> float | None:
    try:
        req = urllib.request.Request(PRICE_URL.format(ref=full_ref), headers=HEADERS)
        data = json.loads(urllib.request.urlopen(req, timeout=15).read())
        return data["price"]["amount"]
    except Exception:
        return None


def our_ap_references() -> list[str]:
    conn = connect()
    rows = conn.execute("""
        SELECT DISTINCT reference_number FROM listings
        WHERE status = 'active' AND brand = 'Audemars Piguet' AND reference_number IS NOT NULL
    """).fetchall()
    return [r[0] for r in rows]


def build() -> list[dict]:
    catalog = fetch_catalog_references()
    results = []
    for short_ref in our_ap_references():
        case_code = short_ref.split(".")[0]
        matches = [f for f in catalog if f.split(".")[0] == case_code]
        if not matches:
            continue
        prices = {m: fetch_price(m) for m in matches}
        distinct_prices = {p for p in prices.values() if p is not None}
        if len(distinct_prices) == 1:
            results.append({
                "brand": "Audemars Piguet",
                "reference_number": short_ref,
                "price": distinct_prices.pop(),
                "currency": "EUR",
                "source": "Audemars Piguet",
                "source_url": f"https://www.audemarspiguet.com/de/de/home.price.{matches[0]}.de.json",
                "checked_date": __import__("datetime").date.today().isoformat(),
            })
        # else: ambiguous (different dial/bracelet variants at different prices) — skip, don't guess
    return results


if __name__ == "__main__":
    found = build()
    print(f"{len(found)} AP references priced directly from audemarspiguet.com")
    for f in found:
        print(" ", f["reference_number"], f["price"])

    path = Path(__file__).resolve().parent.parent / "data" / "official_prices.json"
    existing = json.loads(path.read_text()) if path.exists() else []
    existing = [e for e in existing if e["brand"] != "Audemars Piguet"]
    existing.extend(found)
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
