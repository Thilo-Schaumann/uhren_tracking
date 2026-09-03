"""Exports watches.db into the JSON shape the dashboard artifact embeds.
Run this (from the project root), then build_dashboard.py to produce dashboard.html."""
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from db import connect

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
THUMBNAIL_CACHE = DATA_DIR / "thumbnails_cache.json"
MODEL_VARIANTS = DATA_DIR / "model_variants.json"
BRAND_LOGOS = DATA_DIR / "brand_logos.json"
OFFICIAL_PRICES = DATA_DIR / "official_prices.json"


def _days_between(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def _stats(days: list[int]) -> dict:
    return {
        "sold_count": len(days),
        "avg_days_to_sell": round(sum(days) / len(days)) if days else None,
    }


def build():
    conn = connect()
    thumbnails = json.loads(THUMBNAIL_CACHE.read_text()) if THUMBNAIL_CACHE.exists() else {}
    nicknames = defaultdict(list)
    if MODEL_VARIANTS.exists():
        for v in json.loads(MODEL_VARIANTS.read_text()):
            nicknames[(v["brand"], v["reference_number"])].append(v["nickname"])
    nicknames = {k: " / ".join(dict.fromkeys(v)) for k, v in nicknames.items()}

    official_prices = {}
    if OFFICIAL_PRICES.exists():
        for p in json.loads(OFFICIAL_PRICES.read_text()):
            official_prices[(p["brand"], p["reference_number"])] = {
                "price": p["price"], "source": p["source"],
            }

    active = conn.execute("""
        SELECT l.brand, l.model_line, l.reference_number, p.price, p.currency, l.platform,
               l.condition, l.year, l.band_material, l.dial_color, l.image_url, l.url
        FROM listings l
        JOIN price_snapshots p ON p.listing_id = l.id AND p.date = l.last_seen
        WHERE l.status = 'active' AND l.brand IS NOT NULL AND l.model_line IS NOT NULL
    """).fetchall()

    sold = conn.execute("""
        SELECT brand, model_line, reference_number, first_seen, last_seen
        FROM listings WHERE status = 'sold' AND brand IS NOT NULL AND model_line IS NOT NULL
    """).fetchall()

    all_time_counts = conn.execute("""
        SELECT brand, model_line, COUNT(*) FROM listings
        WHERE brand IS NOT NULL AND model_line IS NOT NULL
        GROUP BY brand, model_line
    """).fetchall()

    sold_days_by_line = defaultdict(list)
    sold_days_by_ref = defaultdict(list)
    for brand, model_line, ref, first_seen, last_seen in sold:
        days = _days_between(first_seen, last_seen)
        sold_days_by_line[(brand, model_line)].append(days)
        if ref:
            sold_days_by_ref[(brand, model_line, ref)].append(days)

    grouped = defaultdict(list)
    for row in active:
        (brand, model_line, ref, price, currency, platform, condition, year,
         band, dial, image, url) = row
        grouped[(brand, model_line)].append({
            "reference_number": ref, "price": price, "currency": currency,
            "platform": platform, "condition": condition, "year": year,
            "band_material": band, "dial_color": dial,
            "image_url": thumbnails.get(image, image), "url": url,
            "nickname": nicknames.get((brand, ref)),
        })

    model_lines = []
    for (brand, model_line), listings in grouped.items():
        prices = [item["price"] for item in listings if item["price"] is not None]
        ref_stats = {
            ref: _stats(days)
            for (b, ml, ref), days in sold_days_by_ref.items()
            if b == brand and ml == model_line
        }
        official = {
            item["reference_number"]: official_prices[(brand, item["reference_number"])]
            for item in listings
            if item["reference_number"] and (brand, item["reference_number"]) in official_prices
        }
        model_lines.append({
            "brand": brand,
            "model_line": model_line,
            "count": len(listings),
            "price_min": min(prices) if prices else None,
            "price_max": max(prices) if prices else None,
            "image_url": next((item["image_url"] for item in listings if item["image_url"]), None),
            **_stats(sold_days_by_line.get((brand, model_line), [])),
            "ref_stats": ref_stats,
            "official_prices": official,
            "listings": listings,
        })
    model_lines.sort(key=lambda m: (m["brand"], m["model_line"]))

    brands = defaultdict(lambda: {"active_count": 0, "prices": [], "model_lines": []})
    for m in model_lines:
        b = brands[m["brand"]]
        b["active_count"] += m["count"]
        if m["price_min"] is not None:
            b["prices"].append(m["price_min"])
        if m["price_max"] is not None:
            b["prices"].append(m["price_max"])
        b["model_lines"].append({"model_line": m["model_line"], "count": m["count"]})

    logos = json.loads(BRAND_LOGOS.read_text()) if BRAND_LOGOS.exists() else {}
    brand_list = [
        {
            "brand": brand,
            "active_count": data["active_count"],
            "price_min": min(data["prices"]) if data["prices"] else None,
            "price_max": max(data["prices"]) if data["prices"] else None,
            "model_lines": sorted(data["model_lines"], key=lambda x: -x["count"]),
            "logo": logos.get(brand),
        }
        for brand, data in brands.items()
    ]
    brand_list.sort(key=lambda b: -b["active_count"])

    top10 = sorted(
        [{"brand": b, "model_line": ml, "count": c} for b, ml, c in all_time_counts],
        key=lambda x: -x["count"],
    )[:10]

    table = [
        {
            "brand": m["brand"], "model_line": m["model_line"],
            "reference_number": item["reference_number"], "nickname": item["nickname"],
            "price": item["price"],
            "currency": item["currency"], "platform": item["platform"],
            "condition": item["condition"], "year": item["year"],
            "band_material": item["band_material"], "dial_color": item["dial_color"],
            "url": item["url"],
            "official_price": m["official_prices"].get(item["reference_number"], {}).get("price"),
        }
        for m in model_lines for item in m["listings"]
    ]

    return {
        "generated_at": date.today().isoformat(),
        "brands": brand_list,
        "model_lines": model_lines,
        "top10": top10,
        "table": table,
    }


if __name__ == "__main__":
    data = build()
    out_path = Path(__file__).resolve().parent / "dashboard_data.json"
    with open(out_path, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"brands={len(data['brands'])} model_lines={len(data['model_lines'])} "
          f"table_rows={len(data['table'])}")
