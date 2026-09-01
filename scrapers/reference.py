"""Best-effort reference-number extraction from a free-text watch title."""
import re

_CANDIDATE = re.compile(r"\b\d{3,6}[A-Z]{0,3}(?:[.\-]\d{1,4})?\b")
_YEAR = re.compile(r"^(19|20)\d{2}$")


def extract_reference_number(title: str) -> str | None:
    candidates = [m for m in _CANDIDATE.findall(title.upper()) if not _YEAR.match(m)]
    if not candidates:
        return None
    return max(candidates, key=len)
