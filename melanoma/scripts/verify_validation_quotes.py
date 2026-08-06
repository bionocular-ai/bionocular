"""
Check that every source_evidence_quote a validation run cites is actually present in
the source document. Offline: no LLM, no network.

A quote that cannot be found in its source is a fabrication - the judge's verdict on
that cell rests on nothing and has to be read by hand.

Usage:
    cd melanoma
    poetry run python3 scripts/verify_validation_quotes.py \
        --validation data/output/Publications_May_2026/validation/validation.json
    poetry run python3 scripts/verify_validation_quotes.py --status FAIL PASS
"""

import argparse
import collections
import csv
import html
import json
import pathlib
import re
import unicodedata

_root = pathlib.Path(__file__).parent.parent

DEFAULT_VALIDATION = (
    _root / "data/output/Publications_May_2026/validation/validation.json"
)

# The judge elides long table rows; each fragment is matched independently.
ELLIPSIS = re.compile(r"\.\.\.|…")
# Quotes reproduce dashes, quote marks and thin spaces inconsistently with the source.
PUNCT_FOLD = {
    "‐": "-",
    "‑": "-",
    "‒": "-",
    "–": "-",
    "—": "-",
    "−": "-",
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "·": ".",
    " ": " ",
    "≥": ">=",
    "≤": "<=",
}
EMPHASIS = re.compile(r"[*`]")
# Sources keep inline markup ("HR<sub>adj</sub>"); the judge quotes it rendered.
HTML_TAG = re.compile(r"</?[a-z]+>", re.I)
MIN_FRAGMENT_CHARS = 12
# Abstract sources hold a whole conference in one file. Without splitting them, a
# quote lifted from a neighbouring abstract would count as found.
ABSTRACT_SECTION = re.compile(r"^### Abstract ID:\s*(\S+)\s*$", re.M)


def normalize(text: str) -> str:
    # Sources carry HTML entities ("p &lt; 0.0001"); the judge quotes the rendered "<".
    text = html.unescape(text)
    text = unicodedata.normalize("NFKC", text)
    for old, new in PUNCT_FOLD.items():
        text = text.replace(old, new)
    # The sources are markdown; the judge quotes the rendered text, so emphasis
    # markers around a word ("*vs*") would otherwise read as a missing quote.
    text = EMPHASIS.sub("", text)
    text = HTML_TAG.sub("", text)
    # Table cell separators are absent from the judge's rendering of a table row.
    text = text.replace("|", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def quote_found(quote: str, source: str) -> bool:
    """True when every non-trivial fragment of the quote appears in the source."""
    fragments = [normalize(f) for f in ELLIPSIS.split(quote)]
    fragments = [f for f in fragments if len(f) >= MIN_FRAGMENT_CHARS]
    if not fragments:
        return True
    return all(fragment in source for fragment in fragments)


def source_text(source_path: pathlib.Path, doc_id: str) -> str | None:
    """The text a quote must appear in: one abstract, or the whole publication."""
    text = source_path.read_text()
    boundaries = list(ABSTRACT_SECTION.finditer(text))
    if not boundaries:
        return text
    abstract_id = doc_id.rsplit("_", 1)[-1]
    for index, match in enumerate(boundaries):
        if match.group(1) != abstract_id:
            continue
        end = (
            boundaries[index + 1].start() if index + 1 < len(boundaries) else len(text)
        )
        return text[match.end() : end]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation", default=str(DEFAULT_VALIDATION))
    parser.add_argument(
        "--status",
        nargs="+",
        default=["FAIL"],
        help="effective_status values to check (default: FAIL)",
    )
    parser.add_argument("--out", default=None, help="CSV of unfound quotes")
    args = parser.parse_args()

    validation_path = pathlib.Path(args.validation)
    data = json.load(open(validation_path))
    wanted = set(args.status)

    sources: dict[str, str] = {}
    missing_sources: list[str] = []
    unfound: list[dict] = []
    counts: collections.Counter = collections.Counter()

    for document in data["documents"]:
        doc_id = document["doc_id"]
        source_path = document.get("source_path")
        if not source_path or not pathlib.Path(source_path).exists():
            missing_sources.append(doc_id)
            continue
        text = source_text(pathlib.Path(source_path), doc_id)
        if text is None:
            missing_sources.append(doc_id)
            continue
        sources[doc_id] = normalize(text)

        for arm in document["arms"]:
            for evaluation in arm["field_evaluations"]:
                if evaluation.get("effective_status") not in wanted:
                    continue
                counts["checked"] += 1
                quote = evaluation.get("source_evidence_quote")
                if not quote:
                    counts["no quote given"] += 1
                    unfound.append(
                        {
                            "doc_id": doc_id,
                            "arm_id": arm["arm_id"],
                            "field_name": evaluation["field_name"],
                            "extracted_value": evaluation.get("extracted_value"),
                            "problem": "no quote given",
                            "quote": "",
                        }
                    )
                    continue
                if quote_found(quote, sources[doc_id]):
                    counts["found"] += 1
                else:
                    counts["not found in source"] += 1
                    unfound.append(
                        {
                            "doc_id": doc_id,
                            "arm_id": arm["arm_id"],
                            "field_name": evaluation["field_name"],
                            "extracted_value": evaluation.get("extracted_value"),
                            "problem": "not found in source",
                            "quote": quote[:500],
                        }
                    )

    print(f"{validation_path.name}: statuses {sorted(wanted)}")
    for key, value in counts.most_common():
        print(f"  {key}: {value}")
    if missing_sources:
        print(
            f"  source file unavailable: {len(missing_sources)} docs ({', '.join(missing_sources)})"
        )

    for row in unfound:
        print(
            f"\n{row['doc_id']} {row['arm_id']} {row['field_name']} = {row['extracted_value']!r}"
            f"  [{row['problem']}]"
        )
        if row["quote"]:
            print(f"  quote: {row['quote']}")

    if args.out:
        with open(args.out, "w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "doc_id",
                    "arm_id",
                    "field_name",
                    "extracted_value",
                    "problem",
                    "quote",
                ],
            )
            writer.writeheader()
            writer.writerows(unfound)
        print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
