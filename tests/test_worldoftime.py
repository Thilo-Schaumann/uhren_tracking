"""Run from the project root:  python3 -m unittest discover -s tests -t .

Parser tests use trimmed copies of real worldoftime.de pages (tests/fixtures); the run-loop
tests drive the whole crawl against a fake fetcher and an in-memory database."""
import contextlib
import io
import re
import unittest
import urllib.error
from pathlib import Path

import db
from scrapers import worldoftime as wot

FX = Path(__file__).parent / "fixtures"
URL = "http://example.test/page"


def fixture(name: str) -> str:
    return (FX / name).read_text(encoding="utf-8")


class ParsingTests(unittest.TestCase):
    def test_parse_price_english_format(self):
        self.assertEqual(wot.parse_price("22,150.-"), 22150.0)
        self.assertEqual(wot.parse_price("\n   22,150.-  \n"), 22150.0)
        self.assertEqual(wot.parse_price("€ 18,750.-"), 18750.0)
        self.assertEqual(wot.parse_price("950.-"), 950.0)
        self.assertEqual(wot.parse_price("22,150.50"), 22150.5)
        self.assertIsNone(wot.parse_price("Sold"))

    def test_classify_price_states(self):
        self.assertEqual(wot.classify_price("22,150.-"), ("price", 22150.0))
        self.assertEqual(wot.classify_price(" Sold "), ("sold", None))
        self.assertEqual(wot.classify_price("Price On Request"), ("on_request", None))
        self.assertEqual(wot.classify_price("???"), ("unknown", None))

    def test_list_page_cards(self):
        cards, bad = wot.parse_list_page(fixture("wot_list_rolex.html"))
        self.assertEqual(bad, 0)
        by_id = {c["wot_id"]: c for c in cards}
        self.assertEqual(set(by_id), {"AB44EC1", "8D38164", "7FE96B2", "2F50827"})

        normal = by_id["AB44EC1"]
        self.assertEqual((normal["model"], normal["reference"], normal["kind"], normal["price"]),
                         ("Daytona Cosmograph", "116520", "price", 22150.0))
        # query string with the neighbour ids is stripped from the detail URL
        self.assertEqual(normal["url"], "https://www.worldoftime.de/Watches/rolex/daytona-cosmograph-AB44EC1")
        self.assertTrue(normal["image_url"].startswith("https://"))

        self.assertEqual((by_id["7FE96B2"]["kind"], by_id["7FE96B2"]["price"]), ("on_request", None))
        self.assertEqual((by_id["2F50827"]["kind"], by_id["2F50827"]["price"]), ("sold", None))

    def test_unparseable_card_is_counted_not_dropped_silently(self):
        html = fixture("wot_list_rolex.html").replace("22,150.-", "???")  # unknown price format
        cards, bad = wot.parse_list_page(html)
        self.assertEqual((len(cards), bad), (3, 1))
        broken, bad2 = wot.parse_list_page('<div class="watch-link"><div class="watch-info-container"></div></div>')
        self.assertEqual((broken, bad2), ([], 1))

    def test_detail_active(self):
        d = wot.parse_detail_page(fixture("wot_detail_active.html"))
        self.assertEqual(d["year"], "2026")
        self.assertEqual(d["condition"], "box and paper, unworn")
        self.assertEqual((d["has_papers"], d["has_box"]), (True, True))
        self.assertEqual(d["dial_color"], "black")
        self.assertEqual(d["band_material"], "heavy oyster bracelet")
        self.assertEqual(d["complication"], "GMT")
        self.assertIn("§ 25", d["price_note"])

    def test_detail_sold_has_no_tax_note_and_por_has_one(self):
        self.assertIsNone(wot.parse_detail_page(fixture("wot_detail_sold.html"))["price_note"])
        por = wot.parse_detail_page(fixture("wot_detail_por.html"))
        self.assertIn("§ 25", por["price_note"])
        self.assertEqual(por["year"], "1990")

    def test_detail_without_rows_is_a_parse_error(self):
        with self.assertRaises(wot.ParseError):
            wot.parse_detail_page("<html><body><p>maintenance</p></body></html>")

    def test_papers_and_box(self):
        self.assertEqual(wot.papers_and_box("box and paper, unworn"), (True, True))
        self.assertEqual(wot.papers_and_box("very nice condition"), (None, None))
        self.assertEqual(wot.papers_and_box(None), (None, None))
        self.assertEqual(wot.papers_and_box("no box, papers"), (True, False))
        # service paper is not the original papers
        self.assertEqual(wot.papers_and_box("very nice condition, service paper"), (None, None))


class FakeResponse:
    def __init__(self, body: str):
        self._body = body.encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code, retry_after=None):
    headers = {"Retry-After": retry_after} if retry_after else {}
    return urllib.error.HTTPError("http://x", code, "err", headers, None)


class PoliteFetcherTests(unittest.TestCase):
    def make(self, outcomes, **kw):
        outcomes = list(outcomes)
        self.sleeps = []

        def opener(req, timeout):
            self.assertEqual(timeout, 20)
            self.assertIn("watch-price-tracker", req.get_header("User-agent"))
            out = outcomes.pop(0)
            if isinstance(out, Exception):
                raise out
            return FakeResponse(out)

        return wot.PoliteFetcher(sleep=self.sleeps.append, rand=lambda a, b: 2.0, opener=opener, **kw)

    def test_pause_between_requests_but_not_before_the_first(self):
        f = self.make(["a", "b"])
        f.get(URL)
        f.get(URL)
        self.assertEqual(self.sleeps, [2.0])

    def test_retries_server_errors_with_backoff_then_succeeds(self):
        f = self.make([http_error(503), urllib.error.URLError("boom"), "ok"])
        self.assertEqual(f.get(URL), "ok")
        self.assertEqual(self.sleeps, [5, 15])

    def test_429_honours_retry_after(self):
        f = self.make([http_error(429, "30"), "ok"])
        self.assertEqual(f.get(URL), "ok")
        self.assertEqual(self.sleeps, [30])

    def test_404_is_not_retried(self):
        f = self.make([http_error(404)])
        with self.assertRaises(wot.FetchError):
            f.get(URL)
        self.assertEqual(self.sleeps, [])

    def test_gives_up_after_all_retries(self):
        f = self.make([http_error(500)] * 4)
        with self.assertRaises(wot.FetchError):
            f.get(URL)
        self.assertEqual(self.sleeps, [5, 15, 45])

    def test_aborts_after_consecutive_failures_instead_of_hammering(self):
        f = self.make([http_error(404)] * 3)
        for _ in range(2):
            with self.assertRaises(wot.FetchError):
                f.get(URL)
        with self.assertRaises(wot.AbortScrape):
            f.get(URL)

    def test_success_resets_the_failure_streak(self):
        f = self.make([http_error(404), "ok", http_error(404), http_error(404), "ok"])
        with self.assertRaises(wot.FetchError):
            f.get(URL)
        f.get(URL)
        for _ in range(2):
            with self.assertRaises(wot.FetchError):
                f.get(URL)
        f.get(URL)  # never reached 3 in a row


class FakeFetcher:
    """Serves list pages by skip= and detail pages by Wot-ID; records every request."""

    def __init__(self, list_pages: dict, details: dict, failing=()):
        self.list_pages, self.details, self.failing = list_pages, details, set(failing)
        self.requests = []

    def get(self, url):
        self.requests.append(url)
        if url in self.failing or any(f in url for f in self.failing):
            raise wot.FetchError(f"{url}: HTTP 500")
        if "/Watches?ManufacturerId=" in url:
            skip = int(re.search(r"skip=(\d+)", url).group(1))
            return self.list_pages[skip]
        return self.details[url.rsplit("-", 1)[-1]]

    def detail_requests(self):
        return [r for r in self.requests if "ManufacturerId" not in r]


CONFIG = {"brands": [{"brand": "Rolex", "manufacturer_id": "mid-rolex", "enabled": True},
                     {"brand": "Omega", "manufacturer_id": "mid-omega", "enabled": False}]}
DETAILS = {"AB44EC1": fixture("wot_detail_active.html"), "8D38164": fixture("wot_detail_active.html"),
           "7FE96B2": fixture("wot_detail_por.html"), "2F50827": fixture("wot_detail_sold.html")}
LIST = fixture("wot_list_rolex.html")


def list_with(html=LIST, **changes):
    """Variant of the list page: {wot_id: 'Sold' / '19,000.-' / None (=remove card)}."""
    cards = re.findall(r'<div class="watch-link.*?(?=<div class="watch-link|</div></body>)', html, re.S)
    out = []
    for card in cards:
        wid = re.search(r"Wot-ID (\w+)", card).group(1)
        if wid in changes:
            if changes[wid] is None:
                continue
            card = re.sub(r'(<p class="m-0 price".*?>)\s*[^<]+?\s*(</p>)', rf"\g<1>{changes[wid]}\g<2>", card, flags=re.S)
        out.append(card)
    return '<html><body><div class="paged-clocks-container grid-view">' + "".join(out) + "</div></body></html>"


class RunLoopTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.err = io.StringIO()
        self._cm = contextlib.ExitStack()
        self._cm.enter_context(contextlib.redirect_stderr(self.err))
        self._cm.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.addCleanup(self._cm.close)

    def run_day(self, day, list_html=LIST, **fetcher_kw):
        fetcher = FakeFetcher({0: list_html}, DETAILS, **fetcher_kw)
        summary = wot.run(self.conn, day, fetcher=fetcher, config=CONFIG)
        return fetcher, summary

    def row(self, wot_id):
        self.conn.row_factory = None
        cur = self.conn.execute(
            "SELECT status, sold_at, first_seen, last_seen, year, price_note, brand, model_line, reference_number, "
            "platform, seller FROM listings WHERE external_id = ?", (wot_id,))
        cols = [d[0] for d in cur.description]
        r = cur.fetchone()
        return dict(zip(cols, r)) if r else None

    def snapshots(self, wot_id):
        return self.conn.execute(
            "SELECT p.date, p.price FROM price_snapshots p JOIN listings l ON l.id = p.listing_id WHERE l.external_id = ?",
            (wot_id,)).fetchall()

    def test_first_run_inserts_open_listings_and_skips_unknown_sold(self):
        fetcher, summary = self.run_day("2026-10-01")
        self.assertEqual(summary["brands"]["Rolex"]["new"], 3)
        self.assertIsNone(self.row("2F50827"))  # "Sold" and never seen open -> no usable dwell time

        active = self.row("AB44EC1")
        self.assertEqual((active["status"], active["platform"], active["seller"]), ("active", "worldoftime", "worldoftime"))
        self.assertEqual((active["brand"], active["reference_number"], active["year"]), ("Rolex", "116520", "2026"))
        self.assertIn("§ 25", active["price_note"])
        self.assertEqual(self.snapshots("AB44EC1"), [("2026-10-01", 22150.0)])

        por = self.row("7FE96B2")
        self.assertEqual(por["status"], "on_request")
        self.assertEqual(self.snapshots("7FE96B2"), [])  # no price is not price 0
        self.assertEqual(len(fetcher.detail_requests()), 3)  # not for the sold one

    def test_second_run_only_uses_list_data_and_keeps_detail_fields(self):
        self.run_day("2026-10-01")
        fetcher, summary = self.run_day("2026-10-02", list_with(AB44EC1="23,000.-"))
        self.assertEqual(fetcher.detail_requests(), [])
        self.assertEqual(summary["brands"]["Rolex"]["updated"], 3)
        row = self.row("AB44EC1")
        self.assertEqual((row["last_seen"], row["year"], row["first_seen"]), ("2026-10-02", "2026", "2026-10-01"))
        self.assertEqual(self.snapshots("AB44EC1"), [("2026-10-01", 22150.0), ("2026-10-02", 23000.0)])

    def test_sold_label_sets_sold_at_but_keeps_last_day_it_was_open(self):
        self.run_day("2026-10-01")
        self.run_day("2026-10-02")
        self.run_day("2026-10-03", list_with(AB44EC1="Sold"))
        row = self.row("AB44EC1")
        self.assertEqual((row["status"], row["sold_at"], row["last_seen"]), ("sold", "2026-10-03", "2026-10-02"))
        # staying "Sold" on the site later must not move last_seen / sold_at
        self.run_day("2026-10-04", list_with(AB44EC1="Sold"))
        row = self.row("AB44EC1")
        self.assertEqual((row["sold_at"], row["last_seen"]), ("2026-10-03", "2026-10-02"))

    def test_listing_that_disappears_is_marked_sold_when_crawl_was_complete(self):
        self.run_day("2026-10-01")
        _, summary = self.run_day("2026-10-02", list_with(**{"8D38164": None}))
        row = self.row("8D38164")
        self.assertEqual((row["status"], row["sold_at"], row["last_seen"]), ("sold", "2026-10-02", "2026-10-01"))
        self.assertEqual(summary["brands"]["Rolex"]["marked_missing"], 1)
        self.assertEqual(self.row("AB44EC1")["status"], "active")

    def test_failed_list_page_never_causes_false_sold(self):
        self.run_day("2026-10-01")
        _, summary = self.run_day("2026-10-02", failing=["skip=0"])
        self.assertFalse(summary["brands"]["Rolex"]["complete"])
        self.assertEqual(self.row("AB44EC1")["status"], "active")
        self.assertIn("list page 1 failed", self.err.getvalue())

    def test_empty_result_is_treated_as_layout_change_not_mass_sold(self):
        self.run_day("2026-10-01")
        _, summary = self.run_day("2026-10-02", "<html><body>maintenance</body></html>")
        self.assertFalse(summary["brands"]["Rolex"]["complete"])
        self.assertEqual(self.row("AB44EC1")["status"], "active")

    def test_sanity_guard_blocks_mass_sold_when_most_listings_vanish(self):
        for i in range(12):
            self.conn.execute(
                "INSERT INTO listings (platform, external_id, seller, brand, url, first_seen, last_seen, status) "
                "VALUES ('worldoftime', ?, 'worldoftime', 'Rolex', 'u', '2026-09-01', '2026-09-30', 'active')", (f"OLD{i}",))
        self.run_day("2026-10-01")
        open_old = self.conn.execute("SELECT COUNT(*) FROM listings WHERE external_id LIKE 'OLD%' AND status = 'active'").fetchone()[0]
        self.assertEqual(open_old, 12)
        self.assertIn("not marking anything as sold", self.err.getvalue())

    def test_por_gets_a_price_later_and_sold_can_come_back(self):
        self.run_day("2026-10-01")
        self.run_day("2026-10-02", list_with(**{"7FE96B2": "19,000.-"}))
        row = self.row("7FE96B2")
        self.assertEqual(row["status"], "active")
        self.assertEqual(self.snapshots("7FE96B2"), [("2026-10-02", 19000.0)])
        self.run_day("2026-10-03", list_with(AB44EC1="Sold"))
        self.run_day("2026-10-04")
        row = self.row("AB44EC1")
        self.assertEqual((row["status"], row["sold_at"]), ("active", None))

    def test_failed_detail_page_skips_that_listing_and_retries_next_run(self):
        _, summary = self.run_day("2026-10-01", failing=["-8D38164"])
        self.assertEqual(summary["brands"]["Rolex"]["detail_failed"], 1)
        self.assertIsNone(self.row("8D38164"))
        self.assertIsNotNone(self.row("AB44EC1"))  # the rest of the run is unaffected
        self.run_day("2026-10-02")
        self.assertIsNotNone(self.row("8D38164"))

    def test_abort_stops_only_this_source_and_keeps_what_was_done(self):
        class Aborting(FakeFetcher):
            def get(self, url):
                if "8D38164" in url:
                    raise wot.AbortScrape("3 in a row")
                return super().get(url)

        fetcher = Aborting({0: LIST}, DETAILS)
        summary = wot.run(self.conn, "2026-10-01", fetcher=fetcher, config=CONFIG)
        self.assertTrue(summary["aborted"])
        self.assertIsNotNone(self.row("AB44EC1"))  # committed before the abort

    def test_disabled_brands_are_not_requested(self):
        fetcher, _ = self.run_day("2026-10-01")
        self.assertFalse(any("mid-omega" in r for r in fetcher.requests))

    def test_manually_excluded_listing_is_neither_inserted_nor_fetched(self):
        original = wot.apply_overrides
        wot.apply_overrides = lambda items: [i for i in items if i["external_id"] != "AB44EC1"]
        self.addCleanup(setattr, wot, "apply_overrides", original)
        fetcher, _ = self.run_day("2026-10-01")
        self.assertIsNone(self.row("AB44EC1"))
        self.assertFalse(any("AB44EC1" in r for r in fetcher.detail_requests()))


class DbTests(unittest.TestCase):
    def test_mark_missing_as_sold_scopes_by_brand_and_covers_on_request(self):
        conn = db.connect(":memory:")
        self.addCleanup(conn.close)
        for ext, brand, status in [("a", "Rolex", "active"), ("b", "Omega", "active"), ("c", "Rolex", "on_request")]:
            conn.execute("INSERT INTO listings (platform, external_id, seller, brand, url, first_seen, last_seen, status) "
                         "VALUES ('p', ?, 's', ?, 'u', '2026-09-01', '2026-09-30', ?)", (ext, brand, status))
        db.mark_missing_as_sold(conn, "p", set(), "2026-10-01", brand="Rolex")
        got = dict(conn.execute("SELECT external_id, status FROM listings").fetchall())
        self.assertEqual(got, {"a": "sold", "b": "active", "c": "sold"})
        self.assertEqual(conn.execute("SELECT sold_at FROM listings WHERE external_id = 'a'").fetchone()[0], "2026-10-01")

    def test_migration_adds_columns_to_an_old_database(self):
        import sqlite3
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute("CREATE TABLE listings (id INTEGER PRIMARY KEY, platform TEXT, external_id TEXT, seller TEXT, "
                     "url TEXT, first_seen TEXT, last_seen TEXT, status TEXT)")
        db._migrate(conn)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(listings)")}
        self.assertTrue({"sold_at", "price_note"} <= cols)


if __name__ == "__main__":
    unittest.main()
