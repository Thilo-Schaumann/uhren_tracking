from .shopify import scrape_shopify_store

BASE_URL = "https://www.colognewatch.de"


def scrape() -> list[dict]:
    return scrape_shopify_store(
        BASE_URL, seller="cologne_watch", shop_display_name="Cologne Watch",
        exclude_product_types={"Uhrenetui"},  # watch cases/rolls, not watches
    )
