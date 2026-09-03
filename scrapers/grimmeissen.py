import re

from bs4 import BeautifulSoup

from .http import fetch_text
from .model_line import extract_model_line

BASE_URL = "https://www.grimmeissen.de"
BRANDS_URL = f"{BASE_URL}/de/marken"

_PRICE = re.compile(r"([\d.]+),(\d{2})\s*€")

_FIELD_MAP = {
    "referenz": "reference_number",
    "zustand": "condition",
    "jahr": "year",
    "armband": "band_material",
    "ziffernblatt": "dial_color",
    "lieferumfang": "_lieferumfang",  # split into has_papers/has_box below
}


def _parse_price(text: str) -> float | None:
    m = _PRICE.search(text)
    if not m:
        return None
    whole = m.group(1).replace(".", "")
    return float(f"{whole}.{m.group(2)}")


def _fetch_detail_specs(detail_url: str) -> dict:
    soup = BeautifulSoup(fetch_text(detail_url), "html.parser")
    raw = {}
    for row in soup.select("table tr"):
        label = row.select_one("th")
        value = row.select_one("td")
        if not label or not value:
            continue
        key = _FIELD_MAP.get(label.get_text(strip=True).lower().rstrip(":"))
        if key:
            raw[key] = value.get_text(strip=True)

    lieferumfang = raw.pop("_lieferumfang", "")
    raw["has_papers"] = "papieren" in lieferumfang.lower() or "papiere" in lieferumfang.lower()
    raw["has_box"] = "box" in lieferumfang.lower()
    return raw


def _brand_slugs() -> list[str]:
    html = fetch_text(BRANDS_URL)
    return sorted(set(re.findall(r"/de/marken/([a-z0-9\-]+)", html)))


def _scrape_listing_page(url: str) -> list[dict]:
    soup = BeautifulSoup(fetch_text(url), "html.parser")
    items = []

    for article in soup.select("article.watch"):
        link = article.select_one("figure a.image")
        img = article.select_one("figure img")
        heading = article.select_one("section.fh h1")
        price_tag = article.select_one("section.fh p")
        if not link or not heading:
            continue

        href = link["href"]
        external_id = href.rstrip("/").rsplit("/", 1)[-1]
        brand_tag = heading.select_one("a")
        brand = brand_tag.get_text(strip=True) if brand_tag else None
        model = heading.get_text(strip=True)
        if brand:
            model = model[len(brand):].strip()
        detail_url = BASE_URL + href
        image_src = (img.get("data-src") or img.get("src")) if img else None

        item = {
            "platform": "grimmeissen",
            "seller": "grimmeissen",
            "external_id": external_id,
            "brand": brand,
            "model": model,
            "model_line": extract_model_line(brand, model),
            "url": detail_url,
            "price": _parse_price(price_tag.get_text()) if price_tag else None,
            "currency": "EUR",
            "image_url": BASE_URL + image_src if image_src else None,
        }
        item.update(_fetch_detail_specs(detail_url))
        items.append(item)

    return items


def scrape() -> list[dict]:
    """Grimmeissen has no single "all watches" page — /de/uhren only shows the
    newest ~35 arrivals. The full catalog (300+) is only reachable by crawling
    every /de/marken/{brand} page."""
    items = {}
    for slug in _brand_slugs():
        for item in _scrape_listing_page(f"{BASE_URL}/de/marken/{slug}"):
            items[item["external_id"]] = item  # de-dupe in case a watch is cross-listed
    return list(items.values())
