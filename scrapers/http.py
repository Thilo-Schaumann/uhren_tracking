"""Shared HTTP helper: sets a normal browser User-Agent and a short timeout."""
import json
import urllib.request

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; watch-price-tracker/1.0)"}


def fetch_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_json(url: str, timeout: int = 20) -> dict:
    return json.loads(fetch_text(url, timeout=timeout))
