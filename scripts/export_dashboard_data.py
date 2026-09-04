"""Exports watches.db into the JSON shape the dashboard artifact embeds.
Run this (from the project root), then build_dashboard.py to produce dashboard.html."""
import json
import re
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


def _normalize_ref(ref: str) -> str:
    """Reference numbers get formatted inconsistently across sources
    ("126710 BLNR" vs "126710BLNR", "PAM368" vs "PAM00368") — normalize
    for matching without touching dashes/dots, which often distinguish
    genuinely different references (e.g. Patek "5712R-001" vs "-010")."""
    if not ref:
        return ""
    r = ref.strip().upper().replace(" ", "")
    m = re.match(r"^PAM0*(\d+)$", r)
    if m:
        return f"PAM{int(m.group(1)):05d}"
    return r


def _load_cluster_specs() -> dict:
    """Merges every data/cluster_specs_*.json (one per researched brand) into
    a single {(brand, normalized_ref): {case_material, bezel_material,
    bracelet_type, size_mm}} lookup."""
    specs = {}
    for path in DATA_DIR.glob("cluster_specs_*.json"):
        for entry in json.loads(path.read_text()):
            key = (entry["brand"], _normalize_ref(entry["reference_number"]))
            specs[key] = {k: v for k, v in entry.items() if k not in ("brand", "reference_number")}
    return specs


def _cluster_label(model_line: str, spec: dict | None) -> str:
    """A model line (e.g. "GMT-Master II") isn't a valid comparison unit on its
    own — steel/ceramic/Oyster and white-gold/Jubilee variants of the "same"
    model line are completely different, non-comparable watches. Where we have
    researched specs for the exact reference, fold them into the label so each
    genuinely comparable configuration gets its own cluster; otherwise fall
    back to the bare model line."""
    if not spec:
        return model_line
    parts = [spec.get("case_material"), spec.get("bezel_material"), spec.get("bracelet_type")]
    parts = [p for p in parts if p]
    if not parts:
        return model_line
    return f"{model_line} {'/'.join(parts)}"


def _days_between(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def _stats(days: list[int]) -> dict:
    return {
        "sold_count": len(days),
        "avg_days_to_sell": round(sum(days) / len(days)) if days else None,
    }


PRICE_BUCKETS = [
    (0, 10_000, "< 10.000 €"),
    (10_000, 25_000, "10.000–25.000 €"),
    (25_000, 50_000, "25.000–50.000 €"),
    (50_000, 100_000, "50.000–100.000 €"),
    (100_000, float("inf"), "> 100.000 €"),
]


def _price_bucket(price: float | None) -> str | None:
    if price is None:
        return None
    for lo, hi, label in PRICE_BUCKETS:
        if lo <= price < hi:
            return label
    return None


def build():
    conn = connect()
    thumbnails = json.loads(THUMBNAIL_CACHE.read_text()) if THUMBNAIL_CACHE.exists() else {}
    cluster_specs = _load_cluster_specs()
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

    def spec_of(brand: str, ref: str) -> dict:
        return cluster_specs.get((brand, _normalize_ref(ref)), {}) if ref else {}

    def cluster_of(brand: str, model_line: str, ref: str) -> str:
        return _cluster_label(model_line, spec_of(brand, ref))

    active = conn.execute("""
        SELECT l.brand, l.model_line, l.reference_number, p.price, p.currency, l.platform,
               l.condition, l.year, l.band_material, l.dial_color, l.has_papers, l.has_box,
               l.complication, l.image_url, l.url
        FROM listings l
        JOIN price_snapshots p ON p.listing_id = l.id AND p.date = l.last_seen
        WHERE l.status = 'active' AND l.brand IS NOT NULL AND l.model_line IS NOT NULL
    """).fetchall()

    sold = conn.execute("""
        SELECT brand, model_line, reference_number, first_seen, last_seen
        FROM listings WHERE status = 'sold' AND brand IS NOT NULL AND model_line IS NOT NULL
    """).fetchall()

    all_time = conn.execute("""
        SELECT brand, model_line, reference_number FROM listings
        WHERE brand IS NOT NULL AND model_line IS NOT NULL
    """).fetchall()

    sold_days_by_cluster = defaultdict(list)
    sold_days_by_ref = defaultdict(list)
    for brand, model_line, ref, first_seen, last_seen in sold:
        days = _days_between(first_seen, last_seen)
        sold_days_by_cluster[(brand, cluster_of(brand, model_line, ref))].append(days)
        if ref:
            sold_days_by_ref[(brand, cluster_of(brand, model_line, ref), ref)].append(days)

    grouped = defaultdict(list)
    family_of_cluster = {}
    for row in active:
        (brand, model_line, ref, price, currency, platform, condition, year,
         band, dial, has_papers, has_box, complication, image, url) = row
        cluster = cluster_of(brand, model_line, ref)
        family_of_cluster[(brand, cluster)] = model_line
        spec = spec_of(brand, ref)
        grouped[(brand, cluster)].append({
            "reference_number": ref, "price": price, "currency": currency,
            "platform": platform, "condition": condition, "year": year,
            "band_material": band, "dial_color": dial,
            "has_papers": has_papers, "has_box": has_box,
            "complication": complication,
            "case_material": spec.get("case_material"),
            "bezel_material": spec.get("bezel_material"),
            "bracelet_type": spec.get("bracelet_type"),
            "image_url": thumbnails.get(image, image), "url": url,
            "nickname": nicknames.get((brand, ref)),
            "price_bucket": _price_bucket(price),
        })

    model_lines = []
    for (brand, cluster), listings in grouped.items():
        prices = [item["price"] for item in listings if item["price"] is not None]
        ref_stats = {
            ref: _stats(days)
            for (b, cl, ref), days in sold_days_by_ref.items()
            if b == brand and cl == cluster
        }
        official = {
            item["reference_number"]: official_prices[(brand, item["reference_number"])]
            for item in listings
            if item["reference_number"] and (brand, item["reference_number"]) in official_prices
        }

        def _representative(field):
            return next((item[field] for item in listings if item.get(field)), None)

        def _representative_known(field):
            """Like _representative, but for has_papers/has_box: False is a
            meaningful known value, not "no data" — don't treat it as falsy."""
            return next((item[field] for item in listings if item.get(field) is not None), None)

        model_lines.append({
            "brand": brand,
            "model_line": cluster,
            "family": family_of_cluster[(brand, cluster)],
            "count": len(listings),
            "price_min": min(prices) if prices else None,
            "price_max": max(prices) if prices else None,
            "image_url": next((item["image_url"] for item in listings if item["image_url"]), None),
            "case_material": _representative("case_material"),
            "bezel_material": _representative("bezel_material"),
            "bracelet_type": _representative("bracelet_type"),
            "dial_color": _representative("dial_color"),
            "condition": _representative("condition"),
            "complication": _representative("complication"),
            "has_papers": _representative_known("has_papers"),
            "has_box": _representative_known("has_box"),
            **_stats(sold_days_by_cluster.get((brand, cluster), [])),
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

    all_time_counts = defaultdict(int)
    for brand, model_line, ref in all_time:
        all_time_counts[(brand, cluster_of(brand, model_line, ref))] += 1
    top10 = sorted(
        [{"brand": b, "model_line": cl, "count": c} for (b, cl), c in all_time_counts.items()],
        key=lambda x: -x["count"],
    )[:10]

    table = [
        {
            "brand": m["brand"], "model_line": m["model_line"], "family": m["family"],
            "reference_number": item["reference_number"], "nickname": item["nickname"],
            "price": item["price"],
            "currency": item["currency"], "platform": item["platform"],
            "condition": item["condition"], "year": item["year"],
            "band_material": item["band_material"], "dial_color": item["dial_color"],
            "case_material": item["case_material"],
            "bezel_material": item["bezel_material"], "bracelet_type": item["bracelet_type"],
            "complication": item["complication"], "price_bucket": item["price_bucket"],
            "has_papers": item["has_papers"], "has_box": item["has_box"],
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
