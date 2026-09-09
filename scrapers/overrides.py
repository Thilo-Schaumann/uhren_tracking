"""Manual, per-listing corrections for cases the scrapers get wrong that can't
be fixed by improving general extraction logic — vendor mis-categorization,
spare parts listed alongside complete watches, marketing names mistaken for
reference numbers. See data/manual_overrides.json for the actual entries."""
import json
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "data" / "manual_overrides.json"


def _load() -> dict:
    if not _PATH.exists():
        return {}
    entries = json.loads(_PATH.read_text())
    return {(e["platform"], e["external_id"]): e for e in entries}


_OVERRIDES = _load()


def apply_overrides(items: list[dict]) -> list[dict]:
    result = []
    for item in items:
        override = _OVERRIDES.get((item["platform"], item["external_id"]))
        if override:
            if override["action"] == "exclude":
                continue
            if override["action"] == "override":
                item[override["field"]] = override["value"]
        result.append(item)
    return result
