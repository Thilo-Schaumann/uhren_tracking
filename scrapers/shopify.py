"""Shared scraper for Shopify shops exposing /collections/{handle}/products.json."""
import re

from .brand_resolver import resolve_brand
from .http import fetch_json
from .model_line import extract_model_line
from .reference import extract_reference_number
from .specs import extract_specs

PAGE_LIMIT = 250
_TAG_STRIP = re.compile(r"<[^>]+>")


def scrape_shopify_store(base_url: str, seller: str, shop_display_name: str, exclude_product_types: set[str] = frozenset()) -> list[dict]:
    """Scrapes the store-wide /products.json feed rather than a single collection —
    a collection like "alle-uhren" or "herrenuhren" is curated by the shop and can
    silently exclude real watches (confirmed missing ~10-20% of inventory at both
    Rothfuss and Cologne Watch)."""
    items = []
    page = 1
    while True:
        url = f"{base_url}/products.json?limit={PAGE_LIMIT}&page={page}"
        data = fetch_json(url)
        products = data.get("products", [])
        if not products:
            break

        for product in products:
            if product.get("product_type") in exclude_product_types:
                continue
            variant = product["variants"][0] if product.get("variants") else {}
            if not variant.get("available", True):
                continue
            title = product.get("title", "")
            brand = resolve_brand(product.get("vendor"), shop_display_name, title)
            description = _TAG_STRIP.sub(" ", product.get("body_html", ""))
            specs = extract_specs(f"{title} {description}")
            images = product.get("images") or []

            items.append({
                "platform": seller,
                "seller": seller,
                "external_id": str(product["id"]),
                "brand": brand,
                "model": title,
                "model_line": extract_model_line(brand, title),
                "reference_number": extract_reference_number(title),
                "url": f"{base_url}/products/{product['handle']}",
                "price": float(variant["price"]) if variant.get("price") else None,
                "currency": "EUR",
                "image_url": images[0]["src"] if images else None,
                **specs,
            })

        if len(products) < PAGE_LIMIT:
            break
        page += 1

    return items
