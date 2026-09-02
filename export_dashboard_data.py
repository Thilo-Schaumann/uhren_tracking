"""Exports watches.db into the JSON shape the dashboard artifact embeds.
Run this, then paste dashboard_data.json's content into the artifact's DATA block."""
import json
from collections import defaultdict
from datetime import date

from db import connect


def _days_between(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def build():
    conn = connect()

    active = conn.execute("""
        SELECT l.brand, l.model_line, l.reference_number, p.price, p.currency, l.platform,
               l.condition, l.year, l.band_material, l.dial_color, l.image_url, l.url
        FROM listings l
        JOIN price_snapshots p ON p.listing_id = l.id AND p.date = l.last_seen
        WHERE l.status = 'active' AND l.brand IS NOT NULL AND l.model_line IS NOT NULL
    """).fetchall()

    sold = conn.execute("""
        SELECT brand, model_line, first_seen, last_seen
        FROM listings WHERE status = 'sold' AND brand IS NOT NULL AND model_line IS NOT NULL
    """).fetchall()

    all_time_counts = conn.execute("""
        SELECT brand, model_line, COUNT(*) FROM listings
        WHERE brand IS NOT NULL AND model_line IS NOT NULL
        GROUP BY brand, model_line
    """).fetchall()

    sold_days = defaultdict(list)
    for brand, model_line, first_seen, last_seen in sold:
        sold_days[(brand, model_line)].append(_days_between(first_seen, last_seen))

    grouped = defaultdict(list)
    for row in active:
        (brand, model_line, ref, price, currency, platform, condition, year,
         band, dial, image, url) = row
        grouped[(brand, model_line)].append({
            "reference_number": ref, "price": price, "currency": currency,
            "platform": platform, "condition": condition, "year": year,
            "band_material": band, "dial_color": dial, "image_url": image, "url": url,
        })

    model_lines = []
    for (brand, model_line), listings in grouped.items():
        days = sold_days.get((brand, model_line), [])
        prices = [item["price"] for item in listings if item["price"] is not None]
        model_lines.append({
            "brand": brand,
            "model_line": model_line,
            "count": len(listings),
            "price_min": min(prices) if prices else None,
            "price_max": max(prices) if prices else None,
            "image_url": next((item["image_url"] for item in listings if item["image_url"]), None),
            "sold_count": len(days),
            "avg_days_to_sell": round(sum(days) / len(days)) if days else None,
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

    brand_list = [
        {
            "brand": brand,
            "active_count": data["active_count"],
            "price_min": min(data["prices"]) if data["prices"] else None,
            "price_max": max(data["prices"]) if data["prices"] else None,
            "model_lines": sorted(data["model_lines"], key=lambda x: -x["count"]),
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
            "reference_number": item["reference_number"], "price": item["price"],
            "currency": item["currency"], "platform": item["platform"],
            "condition": item["condition"], "year": item["year"],
            "band_material": item["band_material"], "dial_color": item["dial_color"],
            "url": item["url"],
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
    with open("dashboard_data.json", "w") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"brands={len(data['brands'])} model_lines={len(data['model_lines'])} "
          f"table_rows={len(data['table'])}")
