"""Deterministic checks on extracted ASH values. They flag for review; extras with a DROP_EXTRA flag are dropped."""

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
# An overall grade >=3 AE field needs an overall AE term in the quote, not one event's name.
_OVERALL_AE_FIELD = re.compile(r"^Grade >=3 (?:AEs|TEAEs|TRAEs)$")
_OVERALL_AE_QUOTE = re.compile(
    r"\bT?[RE]?AEs?\b|adverse (?:events?|reactions?)|toxicit", re.I
)
# Fields tagged with an AE class end their detail with one of these; a class must be
# worded in the abstract, never assumed.
AE_CLASS = re.compile(r"(?:^|; )(TEAE|TRAE|AE|not stated)$")
_CLASS_WORDS = {
    "TEAE": re.compile(r"TEAE|treatment[- ]emergent", re.I),
    "TRAE": re.compile(r"TRAE|(?:treatment|drug)[- ]related|related to", re.I),
    "AE": re.compile(r"\bAEs?\b|adverse event", re.I),
}
# Flags that remove an extra value instead of only marking it.
DROP_EXTRA = {"timepoint_not_in_quote", "not_overall_ae", "mean_not_median"}
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
    if not timepoint_in_quote(field.name, quote):
        flags.append("timepoint_not_in_quote")
    if _OVERALL_AE_FIELD.match(field.name) and not _OVERALL_AE_QUOTE.search(quote):
        flags.append("not_overall_ae")
    if "AE class" in field.detail and "detail" in cell:
        tag = AE_CLASS.search(cell["detail"].strip())
        if not tag:
            flags.append("bad_ae_class")
        elif tag.group(1) in _CLASS_WORDS and not _CLASS_WORDS[tag.group(1)].search(
            text
        ):
            flags.append("ae_class_not_in_abstract")
    if (
        field.name.startswith("Median")
        and re.search(r"\bmean\b", quote, re.I)
        and not re.search(r"median", quote, re.I)
    ):
        flags.append("mean_not_median")
    return flags


def timepoint_in_quote(field_name: str, quote: str) -> bool:
    """A 'rate N mo' field needs N months (or N/12 years) in the quote."""
    m = re.search(r"\b(\d+) mo", field_name)
    if not m:
        return True
    n = int(m.group(1))
    words = [rf"\b{n}[- ]?(?:mo|month)"]
    if n % 12 == 0:
        y = n // 12
        words.append(rf"\b{y}[- ]?(?:y|year)")
        words += [r"\bone[- ]year", r"\b1-?yr"] if y == 1 else []
    return any(re.search(w, quote, re.I) for w in words)


def same_on_arms(family: Family, extracted: dict[str, Any]) -> set[tuple[str, str]]:
    """(arm_id, key) of arm-level values repeated on 2+ arms with the same quote: likely a pooled value copied onto arms."""
    seen: dict[tuple[str, str, str], list[str]] = {}
    for arm_id, cells in extracted.get("arms", {}).items():
        for f in family.fields:
            cell = cells.get(f.key)
            if f.scope == "arm" and cell and cell["value"]:
                seen.setdefault((f.key, cell["value"], cell["quote"]), []).append(
                    arm_id
                )
    return {
        (a, k[0]) for k, arm_ids in seen.items() if len(arm_ids) > 1 for a in arm_ids
    }
