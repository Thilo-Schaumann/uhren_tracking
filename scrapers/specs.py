"""Best-effort extraction of condition/year/papers/box/band/dial from free text
(used for shops that don't expose these as structured fields)."""
import re

CONDITION_PATTERNS = [
    (re.compile(r"like new|neuwertig", re.I), "neuwertig"),
    (re.compile(r"\bnew\b|ungetragen", re.I), "neu"),
    (re.compile(r"sehr gut", re.I), "sehr gut"),
    (re.compile(r"gebraucht|pre-?owned|used", re.I), "gebraucht"),
]

_YEAR = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")

BAND_MATERIALS = [
    "Edelstahl", "Stainless Steel", "Gelbgold", "Yellow Gold", "Weißgold", "White Gold",
    "Roségold", "Rose Gold", "Everose", "Platin", "Platinum", "Titan", "Titanium",
    "Keramik", "Ceramic", "Leder", "Leather", "Kautschuk", "Rubber", "Rolesor", "Stahl",
]

DIAL_COLORS = [
    "Root Beer", "Meteorite", "Ombré", "Panda", "Schwarz", "Black", "Weiß", "White",
    "Blau", "Blue", "Grün", "Green", "Silber", "Silver", "Champagne", "Grau", "Grey",
    "Gray", "Braun", "Brown", "Salmon", "Lachs", "Anthrazit", "Rosa", "Pink",
]

COMPLICATIONS = [
    "Perpetual Calendar", "Ewiger Kalender", "Annual Calendar", "Jahreskalender",
    "Minute Repeater", "Répétition Minutes", "Split-Seconds Chronograph", "Rattrapante",
    "World Time", "Weltzeituhr", "Chronograph", "Chrono", "GMT", "Tourbillon",
    "Moonphase", "Mondphase", "Alarm", "Réveil", "Regulateur",
]


def _first_match(text: str, keywords: list[str]) -> str | None:
    for kw in sorted(keywords, key=len, reverse=True):
        if kw.lower() in text.lower():
            return kw
    return None


def extract_specs(text: str) -> dict:
    condition = None
    for pattern, label in CONDITION_PATTERNS:
        if pattern.search(text):
            condition = label
            break

    year_match = _YEAR.search(text)
    has_full_set = bool(re.search(r"full set", text, re.I))
    has_papers = True if has_full_set or re.search(r"box\s*[&u](nd)?\s*papiere|box and papers", text, re.I) else (
        False if re.search(r"ohne papiere|no papers", text, re.I) else None
    )
    has_box = True if has_full_set or re.search(r"box\s*[&u](nd)?\s*papiere|box and papers", text, re.I) else (
        False if re.search(r"ohne box|no box", text, re.I) else None
    )

    return {
        "condition": condition,
        "year": year_match.group(0) if year_match else None,
        "has_papers": has_papers,
        "has_box": has_box,
        "band_material": _first_match(text, BAND_MATERIALS),
        "dial_color": _first_match(text, DIAL_COLORS),
        "complication": _first_match(text, COMPLICATIONS),
    }
