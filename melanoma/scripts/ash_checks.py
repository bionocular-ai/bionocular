"""Deterministic checks on extracted ASH values. They flag for review; they reject nothing."""

import re
import unicodedata
from typing import Any

from ash_fields import Family, SheetField

_WS = re.compile(r"\s+")
_DASHES = str.maketrans("\u2010\u2011\u2012\u2013\u2014\u2212", "------")
_NUM = r"\d+(?:\.\d+)?"
_TYPE_RE = {
    "percent": re.compile(rf"^{_NUM}$"),
    "months": re.compile(rf"^{_NUM}$"),
    "months_or_nr": re.compile(rf"^(?:{_NUM}|NR)$"),
    "count": re.compile(r"^\d+$"),
    "number": re.compile(rf"^{_NUM}$"),
    "range": re.compile(rf"^{_NUM}-(?:{_NUM}|NE|NR)$"),
    "p_value": re.compile(rf"^[<>=]?\s*{_NUM}$"),
}
# The words a quote must contain for a field about that measure.
_MEASURES = (
    (r"\bPFS\b", r"PFS|progression[- ]free"),
    (r"\bOS\b", r"\bOS\b|overall survival|death"),
    (r"\bEFS\b", r"EFS|event[- ]free"),
    (r"\bRFS\b", r"RFS|relapse[- ]free"),
    (r"\bDFS\b", r"DFS|disease[- ]free"),
    (r"\bLFS\b", r"LFS|leuk[a]?emia[- ]free"),
    (r"\bORR\b", r"ORR|overall response|response rate"),
    (r"\bDOR\b", r"DOR|duration of (?:response|remission)"),
    (r"follow-up", r"follow[- ]?up"),
)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).translate(_DASHES)
    return _WS.sub(" ", s).strip()


def quote_found(quote: str, text: str) -> bool:
    q = _norm(quote)
    return bool(q) and q in _norm(text)


def cell_flags(field: SheetField, cell: dict[str, Any], text: str) -> list[str]:
    """Flags for one filled value. Empty list means nothing to look at."""
    value, quote = str(cell["value"]).strip(), cell["quote"]
    flags = []
    if not quote_found(quote, text):
        flags.append("quote_not_in_abstract")
    pattern = _TYPE_RE.get(field.value_type)
    if pattern and not pattern.match(value):
        flags.append("bad_type")
    elif field.value_type == "percent" and float(value) > 100:
        flags.append("bad_type")
    number = re.search(_NUM, value)
    if (
        pattern
        and number
        and not cell.get("derived")
        and number.group(0) not in _norm(quote).replace(",", "")
    ):
        flags.append("number_not_in_quote")
    for name_re, quote_re in _MEASURES:
        if re.search(name_re, field.name) and not re.search(quote_re, quote, re.I):
            flags.append("measure_not_in_quote")
            break
    return flags


def same_on_arms(family: Family, extracted: dict[str, Any]) -> set[tuple[str, str]]:
    """(arm_id, key) of arm-level values repeated on 2+ arms with the same quote, not marked pooled."""
    seen: dict[tuple[str, str, str], list[str]] = {}
    for arm_id, cells in extracted.get("arms", {}).items():
        for f in family.fields:
            cell = cells.get(f.key)
            if (
                f.scope == "arm"
                and cell
                and cell["value"]
                and cell["basis"] != "pooled"
            ):
                seen.setdefault((f.key, cell["value"], cell["quote"]), []).append(
                    arm_id
                )
    return {
        (a, k[0]) for k, arm_ids in seen.items() if len(arm_ids) > 1 for a in arm_ids
    }
