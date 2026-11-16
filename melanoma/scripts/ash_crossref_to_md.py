"""Convert Crossref JATS abstracts (ASH Blood 2025) to the pipeline's markdown format.

Usage: poetry run python3 scripts/ash_crossref_to_md.py --corpus X.jsonl --ids 94,2264 --out out.md
"""

import argparse
import html
import json
import re
from pathlib import Path

HEADINGS = {
    "introduction": "Introduction",
    "background": "Background",
    "backgroud": "Background",
    "background and significance": "Background",
    "background and objectives": "Background",
    "objective": "Objective",
    "objectives": "Objective",
    "aim": "Objective",
    "aims": "Objective",
    "purpose": "Objective",
    "methods": "Methods",
    "method": "Methods",
    "study design and methods": "Methods",
    "patients and methods": "Methods",
    "materials and methods": "Methods",
    "design and methods": "Methods",
    "results": "Results",
    "resullts": "Results",
    "result": "Results",
    "conclusions": "Conclusions",
    "conclusion": "Conclusions",
    "summary": "Summary",
    "summary and conclusions": "Conclusions",
}
# Longest key first so "patients and methods" wins over any shorter prefix.
_KEYS = "|".join(sorted(map(re.escape, HEADINGS), key=len, reverse=True))
# "Methods and Results:", "Summary of Results:" - a colon is required, the heading is kept as written.
_COMPOUND = re.compile(
    rf"^((?:{_KEYS})\s+(?-i:and|of)\s+[A-Za-z ]{{1,30}}?)\s*[:：]\s*(.*)$", re.I | re.S
)
# A space-separated opener counts only when the next word is not plain lowercase,
# so "Results from the subgroup..." stays prose but "Results mNGS detected..." is a heading.
_OPENER = re.compile(
    rf"^({_KEYS})" r"(?:\s*[:：.]\s*|\s+(?-i:(?![a-z]+\b))|(?-i:(?=[A-Z]))|$)(.*)$",
    re.I | re.S,
)
# Citation-style paragraph: "Surname AB, Surname CD, ... Journal. 2025;16:"
_CITATION = re.compile(r"^(?:[A-Z][\w'-]+ [A-Z]{1,3}, ){2,}")


def _clean(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", "", fragment)
    # some Crossref records are double-escaped (&amp;lt;), so unescape twice
    return " ".join(html.unescape(html.unescape(text)).split())


def jats_to_sections(jats: str) -> list[tuple[str | None, str]]:
    """Return (heading or None, text) per paragraph; trailing reference list dropped."""
    out: list[tuple[str | None, str]] = []
    pending: str | None = None  # heading-only paragraph, applies to the next one
    for raw in re.findall(r"<jats:p>(.*?)</jats:p>", jats, re.S):
        text = _clean(raw)
        if not text:
            continue
        m = _COMPOUND.match(text) or _OPENER.match(text)
        heading = m and HEADINGS.get(m.group(1).lower(), m.group(1))
        if m and not m.group(2).strip():
            pending = heading
            continue
        if m:
            out.append((heading, m.group(2).strip()))
        else:
            out.append((pending, text))
        pending = None
    # ponytail: references are only ever trailing; cut from the first reference-like paragraph
    for i, (_, text) in enumerate(out):
        if re.match(r"references?\b", text, re.I) or _CITATION.match(text):
            return out[:i]
    return out


def render_abstract(
    number: str, title: str, sections: list[tuple[str | None, str]]
) -> str:
    parts = [f"### Abstract ID: {number}\n\n#### Title:\n{title}\n"]
    for heading, text in sections:
        parts.append(f"#### {heading}:\n{text}\n" if heading else f"{text}\n")
    return "\n".join(parts)


def abstract_number(doi: str) -> str | None:
    m = re.fullmatch(r"10\.1182/blood-2025-(\d+)", doi)
    return m.group(1) if m else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True, type=Path)
    ap.add_argument("--ids", required=True)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    wanted = args.ids.split(",")
    found: dict[str, str] = {}
    with args.corpus.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            num = abstract_number(rec.get("DOI", ""))
            if num and num in wanted and rec.get("abstract"):
                title = _clean((rec.get("title") or [""])[0])
                found[num] = render_abstract(
                    num, title, jats_to_sections(rec["abstract"])
                )
    missing = [i for i in wanted if i not in found]
    if missing:
        raise SystemExit(f"ids not found in corpus: {missing}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(found[i] for i in wanted), encoding="utf-8")
    print(f"wrote {len(found)} abstracts to {args.out}")


if __name__ == "__main__":
    main()
