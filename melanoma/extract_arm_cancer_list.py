#!/usr/bin/env python3
"""Extract arm name and cancer type from deployed JSON files into a text file."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data" / "deployed"
OUTPUT_FILE = DATA_DIR / "arm_cancer_type_list.txt"

FILES = [
    "ASCO_2020.json",
    "ASCO_2021.json",
    "ASCO_2022.json",
    "ASCO_2023.json",
    "ASCO_2024.json",
    "ASCO_2025.json",
    "ESMO_2020-2024.json",
    "ESMO_2025.json",
    "Publications_70.json",
    "web_scrape.json",
]


def get_cancer_type(arm_data: dict) -> str:
    """Get cancer type from arm (attributes or top-level), or empty string if missing."""
    # Top-level field used by web_scrape.json
    ct_specific = arm_data.get("cancer_type_specific")
    if ct_specific and str(ct_specific).strip():
        return str(ct_specific).strip()

    attrs = arm_data.get("attributes") or {}
    # ASCO / ESMO older: AttributeType.CANCER_TYPE
    ct = attrs.get("AttributeType.CANCER_TYPE")
    if ct and isinstance(ct, dict) and "value" in ct:
        val = ct["value"]
        if val and val != "Not found":
            return str(val).strip()
        return ""
    # ESMO_2025 / Publications_70: lowercase cancer_type
    ct = attrs.get("cancer_type")
    if ct and isinstance(ct, dict) and "value" in ct:
        val = ct["value"]
        if val and val != "Not found":
            return str(val).strip()
    return ""


def get_items(data: dict) -> list:
    """Return list of items that have arm_results (abstracts, publications, or trials)."""
    return (
        data.get("abstracts")
        or data.get("publications")
        or data.get("trials")
        or []
    )


def section_title(filename: str) -> str:
    """Human-readable section title from filename."""
    base = filename.replace(".json", "").replace("_", " ")
    return base


def main():
    lines = []
    lines.append("Clinical trial arms: arm name and cancer type. Tab-separated.")
    lines.append("Empty cancer_type means not specified in source.")
    lines.append("")
    lines.append("---")
    lines.append("")

    for filename in FILES:
        path = DATA_DIR / filename
        if not path.exists():
            lines.append(f"## {section_title(filename)}")
            lines.append(f"(file not found: {filename})")
            lines.append("")
            continue

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        items = get_items(data)
        rows = []
        for item in items:
            arm_results = item.get("arm_results") or {}
            for arm_key, arm_data in arm_results.items():
                if not isinstance(arm_data, dict):
                    continue
                arm_name = arm_data.get("arm_name") or ""
                cancer_type = get_cancer_type(arm_data)
                rows.append(f"{arm_name}\t{cancer_type}")

        lines.append(f"## {section_title(filename)}")
        lines.append(f"Source: {filename}")
        lines.append("arm_name	cancer_type")
        for row in rows:
            lines.append(row)
        lines.append("")

    OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")
    row_count = sum(
        1 for l in lines if l and "\t" in l and not l.startswith("arm_name\t")
    )
    print(f"Wrote {row_count} rows in {len(FILES)} sections to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
