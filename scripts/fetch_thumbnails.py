"""Downloads referenced watch photos and re-encodes them as small data: URIs,
since published Artifacts cannot hotlink external images (CSP blocks it silently).
Writes a {original_url: data_uri} cache to thumbnails_cache.json, reused across runs
so re-publishing the dashboard doesn't re-download unchanged photos."""
import base64
import io
import json
import sys
import urllib.request
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
CACHE_PATH = HERE.parent / "data" / "thumbnails_cache.json"
MAX_SIZE = 160
JPEG_QUALITY = 68
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; watch-price-tracker/1.0)"}


def to_thumbnail_data_uri(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        raw = urllib.request.urlopen(req, timeout=15).read()
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        img.thumbnail((MAX_SIZE, MAX_SIZE))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception as exc:
        print(f"  failed: {url} ({exc})", file=sys.stderr)
        return None


def build_cache(urls: list[str]) -> dict:
    cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
    todo = [u for u in urls if u and u not in cache]
    print(f"{len(urls)} urls needed, {len(todo)} not cached yet")
    for i, url in enumerate(todo, 1):
        data_uri = to_thumbnail_data_uri(url)
        if data_uri:
            cache[url] = data_uri
        if i % 20 == 0:
            print(f"  {i}/{len(todo)}")
    CACHE_PATH.write_text(json.dumps(cache))
    return cache


if __name__ == "__main__":
    data = json.loads((HERE / "dashboard_data.json").read_text())
    urls = list({m["image_url"] for m in data["model_lines"] if m.get("image_url")})
    build_cache(urls)
    print("done, cache size:", len(json.loads(CACHE_PATH.read_text())))
