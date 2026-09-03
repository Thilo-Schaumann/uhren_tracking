from .shopify import scrape_shopify_store

BASE_URL = "https://rothfuss-watches.de"


def scrape() -> list[dict]:
    return scrape_shopify_store(BASE_URL, seller="rothfuss", shop_display_name="Rothfuss")
