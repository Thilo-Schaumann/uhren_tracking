"""Fetches official logos for watch brands (mostly from Wikimedia Commons, sourced via
Wikidata's P154 "logo image" property) and writes brand_logos.json mapping brand name
-> small base64 data:image/png;base64,... URI (RGBA, transparent background where possible,
longest side <=200px), for use on the dashboard's brand cards.

Progress is written incrementally (after each successful brand) so partial results survive
a failure partway through. Re-running skips brands already present in the output file.
"""
import base64
import io
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "brand_logos.json"
MAX_SIZE = 200
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; watch-price-tracker/1.0; "
    "contact: thilo.schaumann@moebel-schaumann.de)"
}

# Each entry is a direct Wikimedia Commons file title (verified by hand against the
# brand's real logo -- not auto-resolved) so we never guess/mislabel a logo.
BRAND_LOGO_FILES = {
    "Rolex": "Logo da Rolex.png",
    "Audemars Piguet": "Logo Audemars Piguet.svg",
    "Omega": "Omega Logo.svg",
    "Patek Philippe": "Patek Philippe Logo.png",
    "Panerai": "Panerai logo.svg",
    "Breitling": "Breitling Full Logo.png",
    "IWC": "International Watch Company logo.svg",
    "Cartier": "Cartier logo.svg",
    "Jaeger-LeCoultre": "Jaeger-LeCoultre Logo.png",
    "Tudor": "Tudor (Uhrenmarke) logo.svg",
    "A. Lange & Söhne": "Alange soehne logo.svg",
    "Hublot": "Hublot logo.svg",
    "TAG Heuer": "TAG HEUER logo.svg",
    "Piaget": "Piaget logo.svg",
    "Glashütte Original": "Glashütter Uhrenbetrieb logo.svg",
    "Sinn": "Sinn (Uhrenhersteller) logo.svg",
    "Zenith": "Zenith logo.svg",
    "Bell&Ross": "Bellross logo.svg",
    "Bvlgari": "Bulgari logo.svg",
    "Roger Dubuis": "Roger Dubuis Logo.svg",
    "Vacheron Constantin": "Vacheron Constantin logo.png",
    "Breguet": "Breguet logo.png",
    "Chopard": "Logo Chopard.svg",
    "Franck Muller": "Fmlogo.svg",
    "Gerald Charles": "Gerald Charles Genève Black.png",
    "Girard Perregaux": "GP logo Ponts Noir.png",
    "Grand Seiko": "Grand Seiko Logo.svg",
    "H.Moser & Cie.": "H. Moser & Cie Logo.svg",
    "Harry Winston": "Harry Winston Diamond Corporation logo.svg",
    "Longines": "Longines wordmark logo.svg",
    "Montblanc": "Montblanc logo.svg",
    "Parmigiani Fleurier": "Parmigiani Fleurier logo.svg",
    "Richard Mille": "Richard Mille Logo.svg",
    "Tissot": "Tissot Logo (2023).png",
    "Ulysse Nardin": "UN new-logo-mini gris.png",
    # Skipped (see README note in report): "Alain Silberstein", "Cvstos",
    # "Gérald Genta", "Heuer" -- no confidently correct, clean standalone logo found.
}

SKIPPED = {
    "Alain Silberstein": "no logo image on Wikidata/Commons for this designer's brand",
    "Cvstos": "no logo image found on Wikidata/Commons",
    "Gérald Genta": "no logo image found on Wikidata/Commons (only photos of the designer)",
    "Heuer": "no clean standalone pre-1985 Heuer logo found; only a merchandise photo of "
    "stickers, or the modern TAG Heuer mark which would misrepresent the vintage brand",
}


def commons_file_url(filename: str) -> str:
    """Resolve a Commons file title to its actual upload.wikimedia.org URL via the API
    (handles SVGs, which need PNG rendering, and avoids relying on hash-path guessing)."""
    api = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(
        {
            "action": "query",
            "titles": f"File:{filename}",
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": 400,  # ask for a rendered PNG thumbnail; works for SVGs too
            "format": "json",
        }
    )
    req = urllib.request.Request(api, headers=HEADERS)
    data = json.loads(urllib.request.urlopen(req, timeout=20).read())
    pages = data["query"]["pages"]
    for page in pages.values():
        if "imageinfo" not in page:
            raise ValueError(f"no imageinfo for {filename}")
        info = page["imageinfo"][0]
        # Prefer the rendered thumbnail URL (thumburl) since it's a real raster PNG,
        # which Pillow can always read; fall back to the direct file url otherwise.
        return info.get("thumburl") or info["url"]
    raise ValueError(f"file not found: {filename}")


def maybe_key_out_background(img: Image.Image) -> Image.Image:
    """If the image has no real transparency (fully opaque alpha), chroma-key a uniform
    corner-color background (typically white) to transparent, so the logo sits cleanly
    on both light and dark dashboard cards."""
    rgba = img.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getextrema()[0] < 250:
        # already has real transparency
        return rgba

    w, h = rgba.size
    corners = [rgba.getpixel((0, 0)), rgba.getpixel((w - 1, 0)),
               rgba.getpixel((0, h - 1)), rgba.getpixel((w - 1, h - 1))]
    r0, g0, b0, _ = corners[0]
    # only key out if corners roughly agree on a light/uniform color (typical white bg)
    if not all(abs(c[0] - r0) < 12 and abs(c[1] - g0) < 12 and abs(c[2] - b0) < 12
               for c in corners):
        return rgba
    if not (r0 > 235 and g0 > 235 and b0 > 235):
        return rgba

    data = rgba.getdata()
    new_data = []
    for r, g, b, a in data:
        if abs(r - r0) < 18 and abs(g - g0) < 18 and abs(b - b0) < 18:
            new_data.append((r, g, b, 0))
        else:
            new_data.append((r, g, b, a))
    rgba.putdata(new_data)
    return rgba


def to_logo_data_uri(filename: str) -> str:
    url = commons_file_url(filename)
    req = urllib.request.Request(url, headers=HEADERS)
    raw = urllib.request.urlopen(req, timeout=20).read()
    img = Image.open(io.BytesIO(raw))
    img = maybe_key_out_background(img)
    img.thumbnail((MAX_SIZE, MAX_SIZE), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def main():
    result = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else {}
    todo = [b for b in BRAND_LOGO_FILES if b not in result]
    print(f"{len(BRAND_LOGO_FILES)} brands total, {len(todo)} to fetch")

    for i, brand in enumerate(todo, 1):
        filename = BRAND_LOGO_FILES[brand]
        try:
            result[brand] = to_logo_data_uri(filename)
            print(f"  [{i}/{len(todo)}] OK: {brand} ({filename})")
        except Exception as exc:
            print(f"  [{i}/{len(todo)}] FAILED: {brand} ({filename}): {exc}", file=sys.stderr)
        OUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"\ndone. {len(result)}/{len(BRAND_LOGO_FILES)} logos in {OUT_PATH}")
    missing = set(BRAND_LOGO_FILES) - set(result)
    if missing:
        print("missing:", sorted(missing))
    print("\nskipped (no confident logo found):")
    for b, reason in SKIPPED.items():
        print(f"  {b}: {reason}")


if __name__ == "__main__":
    main()
