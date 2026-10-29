"""World of Time (worldoftime.de) — Munich dealer, server-rendered HTML, crawled per brand.

Unlike the other sources this one is polite-by-construction (sequential, randomized
pauses, retry with backoff, bail out instead of hammering) and keeps its own run loop
(`run`) because it needs the database: detail pages are only fetched for Wot-IDs we
don't know yet, and "Sold" / "Price On Request" are first-class states in the list.

Wot-ID (unique per watch) is the external_id. Sold listings stay visible on the site,
so "sold" is detected from the list label as well as from a listing disappearing.
"""
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from db import mark_missing_as_sold, upsert_listing

from .http import HEADERS
from .model_line import extract_model_line
from .overrides import apply_overrides
from .specs import COMPLICATIONS, _first_match

PLATFORM = "worldoftime"
BASE_URL = "https://www.worldoftime.de"
LIST_URL = BASE_URL + "/Watches?ManufacturerId={manufacturer_id}&skip={skip}"
PAGE_SIZE = 24
MAX_PAGES = 60  # hard stop per brand; hitting it counts as "not crawled completely"
CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "worldoftime_brands.json"
DIFF_TAX_NOTE = "§ 25 UStG (Differenzbesteuerung), zzgl. Versand"

# Safety net against a layout change silently turning into mass "sold": if a completely
# crawled brand suddenly shows less than half of what we knew as open, don't mark anything.
MISSING_SANITY_MIN_KNOWN = 10
MISSING_SANITY_RATIO = 0.5


class FetchError(Exception):
    """A single request failed for good (after retries)."""


class AbortScrape(Exception):
    """Too many requests in a row failed — stop instead of hammering the site."""


class ParseError(Exception):
    """A page did not look like what we expect (layout change?)."""


def _log(msg: str):
    print(f"[{PLATFORM}] {msg}")


def _err(msg: str):
    print(f"[{PLATFORM}] ERROR: {msg}", file=sys.stderr)


class PoliteFetcher:
    """Sequential HTTP with a randomized pause between requests, retry + backoff on
    429/5xx/network errors (honouring Retry-After), and an abort after several
    requests in a row that failed for good."""

    def __init__(self, min_delay=1.0, max_delay=3.0, timeout=20, backoff=(5, 15, 45),
                 max_consecutive_failures=3, sleep=time.sleep, rand=random.uniform, opener=None):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.timeout = timeout
        self.backoff = backoff
        self.max_consecutive_failures = max_consecutive_failures
        self._sleep = sleep
        self._rand = rand
        self._open = opener or urllib.request.urlopen
        self._first_request = True
        self.consecutive_failures = 0

    def get(self, url: str) -> str:
        if not self._first_request:
            self._sleep(self._rand(self.min_delay, self.max_delay))
        self._first_request = False

        last_error = None
        for attempt in range(len(self.backoff) + 1):
            wait = None
            try:
                req = urllib.request.Request(url, headers={**HEADERS, "Accept-Language": "en"})
                with self._open(req, timeout=self.timeout) as resp:
                    text = resp.read().decode("utf-8", errors="replace")
                self.consecutive_failures = 0
                return text
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code}"
                if exc.code != 429 and exc.code < 500:
                    break  # 404 & co: retrying won't help
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                if retry_after and retry_after.isdigit():
                    wait = min(int(retry_after), 120)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = str(exc)
            if attempt < len(self.backoff):
                self._sleep(wait if wait is not None else self.backoff[attempt])

        self.consecutive_failures += 1
        if self.consecutive_failures >= self.max_consecutive_failures:
            raise AbortScrape(f"{self.consecutive_failures} requests in a row failed (last: {url}, {last_error})")
        raise FetchError(f"{url}: {last_error}")


# --- parsing ---------------------------------------------------------------

_PRICE = re.compile(r"^([\d,]+)(?:\.(\d{1,2}))?\.?-?$")
_WOT_ID = re.compile(r"^Wot-ID\s+([A-Za-z0-9]+)$")
_REF = re.compile(r"^Ref\.\s*(.+)$")


def _norm(text: str) -> str:
    return " ".join(text.split())


def parse_price(text: str) -> float | None:
    """English number format: '22,150.-' / '€ 18,750.-' -> 22150.0 / 18750.0"""
    m = _PRICE.match(_norm(text).lstrip("€").strip())
    if not m:
        return None
    return float(m.group(1).replace(",", "") + ("." + m.group(2) if m.group(2) else ""))


def classify_price(text: str) -> tuple[str, float | None]:
    """-> (kind, price); kind is 'price' | 'sold' | 'on_request' | 'unknown'"""
    low = _norm(text).lower()
    if low.startswith("sold"):
        return "sold", None
    if low.startswith("price on request"):
        return "on_request", None
    price = parse_price(text)
    return ("price", price) if price is not None else ("unknown", None)


def _parse_card(root) -> dict | None:
    info = root.select_one("div.watch-info-container")
    link = root.find("a", href=re.compile(r"^/Watches/[^/?]+/[^?]+"))
    price_tag = root.select_one("p.price")
    if not (info and link and price_tag):
        return None

    wot_id = reference = None
    brand_text = model = combined = None
    for div in info.select("div.text-truncate"):
        text = _norm(div.get_text())
        classes = set(div.get("class", []))
        if m := _WOT_ID.match(text):
            wot_id = m.group(1)
        elif m := _REF.match(text):
            reference = m.group(1)
        elif "grid-view-hidden" in classes and "list-view-small-hidden" in classes:
            model = text
        elif "grid-view-hidden" in classes:
            brand_text = text
        elif "list-view-hidden" in classes:
            combined = text
    if model is None and combined and brand_text and combined.startswith(brand_text):
        model = combined[len(brand_text):].strip()
    if not (wot_id and model):
        return None

    kind, price = classify_price(price_tag.get_text())
    if kind == "unknown":
        return None

    img = root.find("img")
    image = None
    if img:
        image = img.get("src") if img.get("src") and not img["src"].startswith("data:") else img.get("data-src")
    return {
        "wot_id": wot_id,
        "model": model,
        "reference": reference,
        "kind": kind,
        "price": price,
        "url": urljoin(BASE_URL, link["href"].split("?")[0]),
        "image_url": image,
    }


def parse_list_page(html: str) -> tuple[list[dict], int]:
    """-> (cards, number of cards on the page that could not be parsed)"""
    soup = BeautifulSoup(html, "html.parser")
    cards, bad = [], 0
    for root in soup.select("div.watch-link"):
        card = _parse_card(root)
        if card is None:
            bad += 1
        else:
            cards.append(card)
    return cards, bad


def papers_and_box(condition: str | None) -> tuple[bool | None, bool | None]:
    """-> (has_papers, has_box); None = not stated. 'service paper' is not the original papers."""
    if not condition:
        return None, None
    low = condition.lower()
    papers = True if re.search(r"(?<!service )\bpapers?\b", low) else None
    box = True if re.search(r"\bbox\b", low) else None
    if re.search(r"\bno papers?\b|without papers?|ohne papiere", low):
        papers = False
    if re.search(r"\bno box\b|without box|ohne box", low):
        box = False
    return papers, box


def parse_detail_page(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    rows = {}
    for row in soup.select("div.watch-tabular-details div.row"):
        cols = row.find_all("div", recursive=False)
        if len(cols) >= 2:
            rows[_norm(cols[0].get_text()).lower()] = _norm(cols[1].get_text())
    if not rows:
        raise ParseError("no detail rows found")

    condition = rows.get("condition")
    has_papers, has_box = papers_and_box(condition)
    page_text = soup.get_text(" ")
    return {
        "condition": condition,
        "year": rows.get("year"),
        "dial_color": rows.get("watch face"),
        "band_material": rows.get("watch band"),
        "complication": _first_match(f"{rows.get('movement', '')} {rows.get('description', '')}", COMPLICATIONS),
        "has_papers": has_papers,
        "has_box": has_box,
        "price_note": DIFF_TAX_NOTE if re.search(r"differential taxation|Differenzbesteuerung|§\s*25", page_text) else None,
    }


# --- config & run ----------------------------------------------------------

def load_config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def thumbnails_enabled(path: Path = CONFIG_PATH) -> bool:
    return bool(load_config(path).get("thumbnails", False)) if path.exists() else False


def _crawl_brand(fetcher, brand_cfg: dict, max_pages: int) -> tuple[dict, bool]:
    """-> ({wot_id: card}, complete). `complete` is False if any page failed, any card was
    unparseable, the page cap was hit, or nothing at all came back (likely a layout change)."""
    cards, complete = {}, True
    for page in range(max_pages):
        url = LIST_URL.format(manufacturer_id=brand_cfg["manufacturer_id"], skip=page * PAGE_SIZE)
        try:
            html = fetcher.get(url)
        except FetchError as exc:
            _err(f"{brand_cfg['brand']}: list page {page + 1} failed ({exc})")
            return cards, False
        page_cards, bad = parse_list_page(html)
        if bad:
            _err(f"{brand_cfg['brand']}: {bad} card(s) on list page {page + 1} could not be parsed")
            complete = False
        for card in page_cards:
            cards[card["wot_id"]] = card
        if len(page_cards) + bad < PAGE_SIZE:
            break
    else:
        _err(f"{brand_cfg['brand']}: page cap ({max_pages}) reached, not treating the crawl as complete")
        complete = False
    if not cards:
        _err(f"{brand_cfg['brand']}: no listings found at all, not treating the crawl as complete")
        complete = False
    return cards, complete


def _scrape_brand(conn, today: str, fetcher, brand_cfg: dict, max_pages: int, detail_budget: dict) -> dict:
    brand = brand_cfg["brand"]
    known = {
        external_id: (listing_id, status)
        for external_id, listing_id, status in conn.execute(
            "SELECT external_id, id, status FROM listings WHERE platform = ?", (PLATFORM,)
        )
    }
    open_before = conn.execute(
        "SELECT COUNT(*) FROM listings WHERE platform = ? AND brand = ? AND status IN ('active', 'on_request')",
        (PLATFORM, brand),
    ).fetchone()[0]
    cards, complete = _crawl_brand(fetcher, brand_cfg, max_pages)

    stats = {"new": 0, "updated": 0, "sold": 0, "marked_missing": 0, "detail_failed": 0, "deferred": 0}
    for wot_id, card in cards.items():
        listing_id, status = known.get(wot_id, (None, None))

        if card["kind"] == "sold":
            # Only a listing we saw open has a usable sold date; unknown "Sold" ones are old
            # history with no price and would show up as dwell time 0.
            if listing_id and status in ("active", "on_request"):
                conn.execute("UPDATE listings SET status = 'sold', sold_at = ? WHERE id = ?", (today, listing_id))
                stats["sold"] += 1
            continue

        new_status = "on_request" if card["kind"] == "on_request" else "active"
        if listing_id is None:
            if not apply_overrides([{"platform": PLATFORM, "external_id": wot_id}]):
                continue  # manually excluded
            if detail_budget["left"] is not None and detail_budget["left"] <= 0:
                stats["deferred"] += 1
                continue
            try:
                detail = parse_detail_page(fetcher.get(card["url"]))
            except (FetchError, ParseError) as exc:
                _err(f"{brand}: detail page for {wot_id} failed ({exc}) — retried on the next run")
                stats["detail_failed"] += 1
                continue
            if detail_budget["left"] is not None:
                detail_budget["left"] -= 1
            price_note = detail.pop("price_note")
            item = {
                "platform": PLATFORM, "seller": PLATFORM, "external_id": wot_id,
                "brand": brand, "model": card["model"],
                "model_line": extract_model_line(brand, card["model"]),
                "reference_number": card["reference"],
                "url": card["url"], "image_url": card["image_url"],
                "price": card["price"], "currency": "EUR",
                **detail,
            }
            (item,) = apply_overrides([item])
            new_id = upsert_listing(conn, item, today)
            conn.execute(
                "UPDATE listings SET status = ?, price_note = ?, sold_at = NULL WHERE id = ?",
                (new_status, price_note, new_id),
            )
            stats["new"] += 1
        else:
            # Known listing: list data is enough. Don't go through upsert_listing — it would
            # overwrite the detail-page fields with None.
            conn.execute(
                "UPDATE listings SET last_seen = ?, status = ?, sold_at = NULL WHERE id = ?",
                (today, new_status, listing_id),
            )
            if card["price"] is not None:
                conn.execute(
                    "INSERT OR REPLACE INTO price_snapshots (listing_id, date, price, currency) VALUES (?, ?, ?, 'EUR')",
                    (listing_id, today, card["price"]),
                )
            stats["updated"] += 1

    if complete:
        if open_before >= MISSING_SANITY_MIN_KNOWN and len(cards) < open_before * MISSING_SANITY_RATIO:
            _err(f"{brand}: only {len(cards)} listings found vs {open_before} open in the DB — "
                 "not marking anything as sold (layout change?)")
        else:
            before = conn.execute(
                "SELECT COUNT(*) FROM listings WHERE platform = ? AND brand = ? AND status = 'sold'", (PLATFORM, brand)
            ).fetchone()[0]
            mark_missing_as_sold(conn, PLATFORM, set(cards), today, brand=brand)
            after = conn.execute(
                "SELECT COUNT(*) FROM listings WHERE platform = ? AND brand = ? AND status = 'sold'", (PLATFORM, brand)
            ).fetchone()[0]
            stats["marked_missing"] = after - before
    else:
        _err(f"{brand}: crawl incomplete — not checking for disappeared listings")

    _log(f"{brand}: {len(cards)} on site — " + ", ".join(f"{k} {v}" for k, v in stats.items() if v))
    return {"complete": complete, **stats}


def run(conn, today: str, fetcher: PoliteFetcher | None = None, config: dict | None = None,
        max_pages: int = MAX_PAGES, max_details: int | None = None) -> dict:
    """Crawl all enabled brands. Never raises for site trouble: a broken page is logged and
    skipped, repeated failures stop only this source. `max_details` caps detail-page fetches
    (smoke tests)."""
    fetcher = fetcher or PoliteFetcher()
    config = config if config is not None else load_config()
    detail_budget = {"left": max_details}
    summary = {"brands": {}, "aborted": False}
    for brand_cfg in config["brands"]:
        if not brand_cfg.get("enabled"):
            continue
        try:
            summary["brands"][brand_cfg["brand"]] = _scrape_brand(conn, today, fetcher, brand_cfg, max_pages, detail_budget)
        except AbortScrape as exc:
            _err(f"aborting World of Time run: {exc}")
            summary["aborted"] = True
            break
        finally:
            conn.commit()
    return summary
