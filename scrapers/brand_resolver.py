"""Fixes bad vendor/brand data from shop product feeds.

Two known failure modes seen in scraped Shopify data:
1. The shop sets its own name as `vendor` instead of the watch's actual
   manufacturer (e.g. Cologne Watch tagging its own listings "Cologne Watch").
2. The shop sets a livery/special-edition name as `vendor` instead of the
   manufacturer (e.g. a Porsche Design x Martini Racing chronograph tagged
   just "Martini Racing").

Both are fixed by re-deriving the brand from the listing title, matched
against a curated list of known watch manufacturers.
"""

# Explicit fixes for vendor strings that aren't a shop's own name but are
# still wrong (not the manufacturer) — checked before the generic fallback.
VENDOR_OVERRIDES = {
    "martini racing": "Porsche Design",
}

# Canonical display names for brands that show up in scraped titles but
# aren't already covered by scrapers.model_line.MODEL_LINES.
KNOWN_BRANDS = [
    "Rolex", "Omega", "Patek Philippe", "Audemars Piguet", "Panerai", "IWC",
    "Cartier", "Jaeger-LeCoultre", "Tudor", "A. Lange & Söhne", "Hublot",
    "Breitling", "TAG Heuer", "Heuer", "Piaget", "Glashütte Original", "Sinn",
    "Zenith", "Bell & Ross", "Bell&Ross", "Bvlgari", "Roger Dubuis",
    "Vacheron Constantin", "Alain Silberstein", "Breguet", "Chopard", "Cvstos",
    "Franck Muller", "Gerald Charles", "Girard Perregaux", "Grand Seiko",
    "Gérald Genta", "H.Moser & Cie.", "Harry Winston", "Longines",
    "Montblanc", "Parmigiani Fleurier", "Richard Mille", "Tissot",
    "Ulysse Nardin", "Eberhard & Co.", "Porsche Design", "Junghans",
    "Nomos Glashütte", "Oris", "Rado", "Seiko", "Citizen", "Baume & Mercier",
    "Maurice Lacroix", "Frederique Constant", "Blancpain",
]


def _brand_from_title(title: str) -> str | None:
    normalized = title.lower()
    for brand in sorted(KNOWN_BRANDS, key=len, reverse=True):
        if normalized.startswith(brand.lower()):
            return brand
    return None


def resolve_brand(vendor: str, shop_name: str, title: str) -> str:
    if not vendor:
        return _brand_from_title(title) or vendor

    key = vendor.strip().lower()
    if key in VENDOR_OVERRIDES:
        return VENDOR_OVERRIDES[key]
    if key == shop_name.strip().lower():
        return _brand_from_title(title) or vendor
    return vendor
