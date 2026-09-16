#!/usr/bin/env python3
"""Turn parsed SITC supplement markdown into the abstract-pipeline format.

Input is the page-level markdown a PDF parser produced from a SITC abstract
supplement (`data/processed/SITC_Abstracts/SITC_<year>.md`). Output is the
`### Abstract ID:` / `#### Section:` layout `run_abstract_pipeline.py` splits on
(see `data/postprocessed/ESMO_Abstracts/` for the reference shape).

Per abstract: keep the title, Background/Methods/Results/Conclusions, tables that
carry an "Abstract N Table M" caption, and every NCT id found anywhere in the
abstract. Drop authors, affiliations, figures, figure-derived tables, references,
ethics/consent/acknowledgements, running headers and DOI lines.

Usage:
    cd melanoma
    poetry run python3 scripts/postprocess_sitc_abstracts.py \\
        --in  data/processed/SITC_Abstracts/SITC_2025.md \\
        --out data/postprocessed/SITC_Abstracts/SITC_2025.md \\
        --keep 22,38,41,90
"""

import argparse
import re
from pathlib import Path

# An abstract starts with its number, either alone on a line or leading a heading.
NUMBER_LINE = re.compile(r"^\**(\d{1,4})\**$")
HEADING = re.compile(r"^#{1,3}\s+(.*)$")
HEADING_WITH_NUMBER = re.compile(r"^#{1,3}\s+\**(\d{1,4})\**\s+\**(.+?)\**$")
SECTION = re.compile(r"^\*\*([A-Z][A-Za-z ]+?)\*\*\s*(.*)$")
TABLE_CAPTION = re.compile(r"^\*\*Abstract \d+ Table \d+\*\*")
NCT = re.compile(r"NCT\s?(\d{8})")

KEEP_SECTIONS = (
    "Background",
    "Methods",
    "Results",
    "Results and Conclusions",
    "Conclusions",
)
NOISE = re.compile(
    r"^(Abstracts|A\d{1,4}|<?http\S*>?|\*?J Immunother Cancer\*? .*|\!\[.*)$"
)
MATH = re.compile(r"\$([^$]+)\$")
MATH_TOKENS = {
    "\\alpha": "α",
    "\\beta": "β",
    "\\gamma": "γ",
    "\\Delta": "Δ",
    "\\pm": "±",
    "\\geq": "≥",
    "\\ge": "≥",
    "\\leq": "≤",
    "\\le": "≤",
    "\\times": "×",
    "\\%": "%",
}


def unmath(m: re.Match) -> str:
    """Render a $...$ span as plain text: greek/operators, x^{n} -> x^n, no spaces."""
    text = m.group(1)
    for tok, char in MATH_TOKENS.items():
        text = text.replace(tok, char)
    text = re.sub(r"\^\{([^}]*)\}", r"^\1", text)
    return text.replace(" ", "")


def clean(text: str) -> str:
    text = re.sub(r"</?su[bp]>", "", text)
    text = MATH.sub(unmath, text)
    text = text.replace("\\*", "*")
    return re.sub(r"\s{2,}", " ", text).strip()


def clean_row(line: str) -> str:
    return re.sub(r"<br/?>|</?[bi]>", " ", MATH.sub(unmath, line)).strip()


def join_paragraphs(paragraphs: list[str]) -> str:
    """Paragraph breaks that fall mid-sentence are page/column breaks; glue them."""
    out: list[str] = []
    for p in paragraphs:
        if not p:
            continue
        if out and not out[-1].endswith((".", ":", ")", "%")):
            out[-1] += " " + p
        else:
            out.append(p)
    return "\n\n".join(out)


def split_abstracts(lines: list[str]) -> list[tuple[str, str, list[str]]]:
    """Yield (number, title, body_lines) for every abstract in the file."""
    abstracts: list[tuple[str, str, list[str]]] = []
    pending_number: str | None = None
    for line in lines:
        line = line.rstrip()
        if m := NUMBER_LINE.match(line):
            pending_number = m.group(1)
            continue
        if pending_number and (m := HEADING.match(line)):
            abstracts.append((pending_number, clean(m.group(1).strip("*")), []))
            pending_number = None
            continue
        if m := HEADING_WITH_NUMBER.match(line):
            abstracts.append((m.group(1), clean(m.group(2)), []))
            continue
        if abstracts:
            abstracts[-1][2].append(line)
    return abstracts


def render(number: str, title: str, body: list[str]) -> str:
    sections: dict[str, list[str]] = {}
    tables: list[str] = []
    current: str | None = None
    seen_authors = False
    in_table = False
    for line in body:
        if not line or NOISE.match(line):
            continue
        if not seen_authors:  # first paragraph after the title is authors/affiliations
            seen_authors = True
            continue
        if TABLE_CAPTION.match(line):
            tables.append(clean(line))
            in_table = True
            continue
        if line.startswith("|"):
            # Rows directly under an "Abstract N Table M" caption belong to it;
            # a table with no caption is a parser rendering of a figure - drop it.
            if in_table:
                tables[-1] += "\n" + clean_row(line)
            continue
        in_table = False
        if m := SECTION.match(line):
            label = m.group(1)
            current = label if label in KEEP_SECTIONS else None
            if current:
                sections.setdefault(current, []).append(clean(m.group(2)))
            continue
        if current and not line.startswith("#"):
            sections[current].append(clean(line))

    ncts = sorted({f"NCT{n}" for n in NCT.findall("\n".join(body))})
    out = [f"### Abstract ID: {number}", "", "#### Title:", title, ""]
    for label in KEEP_SECTIONS:
        if label in sections:
            out += [f"#### {label}:", join_paragraphs(sections[label]), ""]
    for table in tables:
        out += [table, ""]
    out += [
        "#### Clinical trial identification:",
        ", ".join(ncts) or "None",
        "",
        "---",
        "",
    ]
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--in", dest="in_path", type=Path, required=True)
    parser.add_argument("--out", dest="out_path", type=Path, required=True)
    parser.add_argument("--keep", help="comma-separated abstract numbers; default all")
    args = parser.parse_args()

    keep = set(args.keep.split(",")) if args.keep else None
    abstracts = split_abstracts(args.in_path.read_text(encoding="utf-8").splitlines())
    selected = [a for a in abstracts if keep is None or a[0] in keep]
    if keep:
        missing = keep - {a[0] for a in selected}
        if missing:
            raise SystemExit(f"abstracts not found in input: {sorted(missing)}")

    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    args.out_path.write_text("\n".join(render(*a) for a in selected), encoding="utf-8")
    print(
        f"{len(selected)} abstracts written to {args.out_path} (found {len(abstracts)} in input)"
    )


if __name__ == "__main__":
    main()
