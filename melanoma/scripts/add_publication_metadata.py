#!/usr/bin/env python3
"""Inject a # Metadata section into postprocessed publication markdowns.

Reads from data/processed/Publications/, adds a structured metadata block,
writes to data/postprocessed/Publications/. Idempotent — strips any existing
# Metadata block before re-injecting so re-runs are safe.

Usage:
    cd melanoma && poetry run python3 scripts/add_publication_metadata.py
"""

import re
import sys
from pathlib import Path

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed" / "Publications"
POSTPROCESSED_DIR = (
    Path(__file__).parent.parent / "data" / "postprocessed" / "Publications"
)

# Strip an existing # Metadata block (including preceding blank line) before re-injecting
_EXISTING_META_RE = re.compile(r"\n+# Metadata\n.*?(?=\n# |\Z)", re.DOTALL)

# Any 4-digit year in the range 1990–2029
_YEAR_RE = re.compile(r"\b((?:199|20[012])\d)\b")


def _extract_year(text: str) -> str | None:
    m = _YEAR_RE.search(text)
    return m.group(1) if m else None


def _find_year_nearby(lines: list[str], idx: int, window: int = 10) -> str | None:
    """Scan `window` lines before and after `idx` for the closest year."""
    # Search above first (preferred — user confirmed year is usually above)
    for i in range(idx - 1, max(-1, idx - window - 1), -1):
        y = _extract_year(lines[i])
        if y:
            return y
    # Fall back to below (e.g. © copyright line after JCO citation)
    for i in range(idx + 1, min(len(lines), idx + window + 1)):
        y = _extract_year(lines[i])
        if y:
            return y
    return None


def find_citation(text: str) -> tuple[str, str, str] | None:
    """Return (journal, citation_line, year) or None.

    Citation formats handled:
    1. "N Engl J Med 2015;373:23-34." — year in citation
    2. "Annals of Oncology 28: 2581-2587, 2017" — year at end
    3. "European Journal of Cancer 86 (2017) 37-45" — year in parens after vol
    4. "Journal for ImmunoTherapy of Cancer (2019) 7:49" — year in parens before vol
    5. "Annals of Oncology | Volume 32 | Issue 10 | 2021" — pipe-separated
    6. "Lancet Oncol 2018" — year, no volume
    7. "J Clin Oncol 36:383-390." — no year; year in lines above
    8. "J Clin Oncol 18:158-166. © 2000 ..." — year in same-line copyright
    9. "Clin Cancer Res Published OnlineFirst June 30, 2020." — year in text
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or not s[0].isupper():
            continue

        # Pattern 8: same-line copyright "J Clin Oncol 18:158-166. © 2000 ..."
        m = re.match(r"^(J Clin Oncol \d+[:\d\-–]+\.?)\s*[©@]\s*(\d{4})", s)
        if m:
            return "J Clin Oncol", m.group(1).rstrip(".") + ".", m.group(2)

        # Pattern 0: "JAMA. 2011;305(22):2327-2334" — dot after short journal abbreviation
        m = re.match(r"^([A-Z][A-Za-z\s]*[A-Za-z])\.\s+(\d{4})[;:]\s*\d+", s)
        if m:
            journal = m.group(1).strip()
            return journal, s, m.group(2)

        # Pattern 1: "Journal YEAR;vol:pages" or "Journal YEAR; vol: pages"
        # Allows commas in journal name (e.g. "Cancer Immunology, Immunotherapy")
        m = re.match(r"^([A-Z][A-Za-z,\s]+?)\s{1,3}(\d{4})[;:]\s*\d+", s)
        if m:
            return m.group(1).strip(), s, m.group(2)

        # Pattern 2: "Journal vol: pages, YEAR"
        m = re.match(r"^([A-Z][A-Za-z,\s]+?)\s+\d+[:\s].+?,\s*(\d{4})\s*$", s)
        if m:
            return m.group(1).strip(), s, m.group(2)

        # Pattern 3: "Journal vol (YEAR) pages"
        m = re.match(r"^([A-Z][A-Za-z,\s]+?)\s+\d+\s+\((\d{4})\)", s)
        if m:
            return m.group(1).strip(), s, m.group(2)

        # Pattern 4: "Journal (YEAR) vol:pages" — JITC style
        m = re.match(r"^([A-Z][A-Za-z,\s]+?)\s+\((\d{4})\)\s*\d+", s)
        if m:
            return m.group(1).strip(), s, m.group(2)

        # Pattern 5: pipe-separated "Journal | Vol N | ..." — year anywhere in line
        # Handles "Annals of Oncology | Volume 32 | Issue 10 | 2021"
        # and "Nature | Vol 611 | 3 November 2022"
        m = re.match(r"^([A-Z][A-Za-z,\s]+?)\s+\|", s)
        if m:
            year = _extract_year(s)
            if year:
                return m.group(1).strip(), s, year

        # Pattern 6: "Journal YEAR" — year only, no volume
        m = re.match(r"^([A-Z][A-Za-z,\s]+?)\s{1,3}(\d{4})\s*$", s)
        if m:
            return m.group(1).strip(), s, m.group(2)

        # Pattern 7a: "Cancer Discov; vol(issue); pages" — semicolon format
        m = re.match(r"^([A-Z][A-Za-z\s]+?);\s*\d+\(", s)
        if m:
            year = _find_year_nearby(lines, i)
            if year:
                return m.group(1).strip(), s, year

        # Pattern 7b: "Journal vol:pages" without year — look nearby for year
        # Also handles "J Clin Oncol 38." (volume only, no pages)
        m = re.match(r"^([A-Z][A-Za-z\s]+?)\s+\d+(?:[:\-–][\d\-–]+)?\.?\s*$", s)
        if m:
            year = _find_year_nearby(lines, i) or _extract_year(s)
            if year:
                return m.group(1).strip(), s, year

        # Pattern 9: "Clin Cancer Res Published OnlineFirst ... YEAR"
        # Only match if each word starts with uppercase (journal abbreviation),
        # avoiding false match on "This article was published on..."
        m = re.match(r"^([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})\s+Published\b", s)
        if m:
            year = _extract_year(s)
            if year:
                citation = m.group(1).strip()
                return citation, citation, year

    return None


def inject_metadata(text: str, journal: str, citation: str, year: str) -> str:
    text = _EXISTING_META_RE.sub("", text)
    metadata_block = (
        f"\n\n# Metadata\n"
        f"journal: {journal}\n"
        f"citation: {citation}\n"
        f"year: {year}\n"
    )
    first_newline = text.find("\n")
    if first_newline == -1:
        return text + metadata_block + "\n"
    rest = text[first_newline:].lstrip("\n")
    return text[:first_newline] + metadata_block + "\n" + rest


def process_file(src: Path, dst: Path) -> str:
    text = src.read_text(encoding="utf-8")
    result = find_citation(text)
    if result is None:
        return "no_citation"
    journal, citation, year = result
    updated = inject_metadata(text, journal, citation, year)
    dst.write_text(updated, encoding="utf-8")
    return "ok"


def main() -> None:
    POSTPROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(PROCESSED_DIR.glob("*.md"))
    if not files:
        print(f"No .md files found in {PROCESSED_DIR}", file=sys.stderr)
        sys.exit(1)

    counts: dict[str, int] = {"ok": 0, "no_citation": 0, "error": 0}
    failed: list[str] = []
    no_citation: list[str] = []

    for src in files:
        dst = POSTPROCESSED_DIR / src.name
        try:
            status = process_file(src, dst)
        except Exception as exc:
            status = "error"
            failed.append(f"{src.name}: {exc}")
        if status == "no_citation":
            no_citation.append(src.name)
        counts[status] += 1

    total = len(files)
    print(
        f"Done. {total} files — "
        f"{counts['ok']} injected, "
        f"{counts['no_citation']} no citation found, "
        f"{counts['error']} errors"
    )
    if failed:
        print("Errors:")
        for f in failed:
            print(f"  {f}")
    if no_citation:
        print("No citation found — check manually:")
        for name in no_citation:
            print(f"  {name}")


if __name__ == "__main__":
    main()
