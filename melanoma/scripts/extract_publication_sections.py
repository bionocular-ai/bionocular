"""Extract all sections and subsections from postprocessed publication markdown files.

Usage:
    poetry run python3 scripts/extract_publication_sections.py [--output OUTPUT]

Writes JSON: list of {file, sections: [{level, heading}]}
Prints tree summary to stdout.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_HEADER_RE = re.compile(r"^(#+)\s+(.*?)\s*$")
_PUBLICATIONS_DIR = (
    Path(__file__).parent.parent / "data" / "postprocessed" / "Publications"
)


def extract_sections(path: Path) -> list[dict]:
    sections = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _HEADER_RE.match(line)
        if m:
            level = len(m.group(1))
            heading = re.sub(r"\*+", "", m.group(2)).strip()
            sections.append({"level": level, "heading": heading})
    return sections


def print_tree(file: str, sections: list[dict]) -> None:
    print(f"\n{file}")
    for s in sections:
        indent = "  " * (s["level"] - 1)
        marker = "#" * s["level"]
        print(f"  {indent}{marker} {s['heading']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", "-o", help="Write JSON to this file (default: stdout only)"
    )
    parser.add_argument(
        "--dir", default=str(_PUBLICATIONS_DIR), help="Publications directory"
    )
    args = parser.parse_args()

    pub_dir = Path(args.dir)
    if not pub_dir.is_dir():
        print(f"ERROR: directory not found: {pub_dir}", file=sys.stderr)
        sys.exit(1)

    files = sorted(pub_dir.glob("*.md"))
    if not files:
        print(f"ERROR: no .md files in {pub_dir}", file=sys.stderr)
        sys.exit(1)

    results = []
    for path in files:
        sections = extract_sections(path)
        results.append({"file": path.name, "sections": sections})
        print_tree(path.name, sections)

    print(
        f"\n--- {len(files)} files, {sum(len(r['sections']) for r in results)} total headers ---"
    )

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"JSON written to {out_path}")
    else:
        print("\nJSON output (use --output FILE to save):")
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
