"""Shared scraper for Shopify shops exposing /collections/{handle}/products.json."""
from .http import fetch_json
from .reference import extract_reference_number

PAGE_LIMIT = 250


def scrape_shopify_collection(base_url: str, collection_handle: str, seller: str) -> list[dict]:
    items = []
    page = 1
    while True:
        url = f"{base_url}/collections/{collection_handle}/products.json?limit={PAGE_LIMIT}&page={page}"
        data = fetch_json(url)
        products = data.get("products", [])
        if not products:
            break

        for product in products:
            variant = product["variants"][0] if product.get("variants") else {}
            if not variant.get("available", True):
                continue
            title = product.get("title", "")
            items.append({
                "platform": seller,
                "seller": seller,
                "external_id": str(product["id"]),
                "brand": product.get("vendor"),
                "model": title,
                "reference_number": extract_reference_number(title),
                "url": f"{base_url}/products/{product['handle']}",
                "price": float(variant["price"]) if variant.get("price") else None,
                "currency": "EUR",
            })

        if len(products) < PAGE_LIMIT:
            break
        page += 1

    return items
