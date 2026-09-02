from .shopify import scrape_shopify_collection

BASE_URL = "https://rothfuss-watches.de"
COLLECTION = "alle-uhren"


def scrape() -> list[dict]:
    return scrape_shopify_collection(BASE_URL, COLLECTION, seller="rothfuss", shop_display_name="Rothfuss")
