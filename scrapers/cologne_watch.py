from .shopify import scrape_shopify_collection

BASE_URL = "https://www.colognewatch.de"
COLLECTION = "herrenuhren"


def scrape() -> list[dict]:
    return scrape_shopify_collection(BASE_URL, COLLECTION, seller="cologne_watch", shop_display_name="Cologne Watch")
