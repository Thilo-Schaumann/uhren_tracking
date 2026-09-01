import re

from bs4 import BeautifulSoup

from .http import fetch_text

BASE_URL = "https://www.grimmeissen.de"
LISTING_URL = f"{BASE_URL}/de/uhren"

_PRICE = re.compile(r"([\d.]+),(\d{2})\s*€")


def _parse_price(text: str) -> float | None:
    m = _PRICE.search(text)
    if not m:
        return None
    whole = m.group(1).replace(".", "")
    return float(f"{whole}.{m.group(2)}")


def _fetch_reference_number(detail_url: str) -> str | None:
    soup = BeautifulSoup(fetch_text(detail_url), "html.parser")
    for row in soup.select("table tr"):
        label = row.select_one("th")
        value = row.select_one("td")
        if label and value and "referenz" in label.get_text(strip=True).lower():
            return value.get_text(strip=True)
    return None


def scrape() -> list[dict]:
    html = fetch_text(LISTING_URL)
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for article in soup.select("article.watch"):
        link = article.select_one("figure a.image")
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

        items.append({
            "platform": "grimmeissen",
            "seller": "grimmeissen",
            "external_id": external_id,
            "brand": brand,
            "model": model,
            "reference_number": _fetch_reference_number(detail_url),
            "url": detail_url,
            "price": _parse_price(price_tag.get_text()) if price_tag else None,
            "currency": "EUR",
        })

    return items
