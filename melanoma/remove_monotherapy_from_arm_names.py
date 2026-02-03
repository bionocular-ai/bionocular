#!/usr/bin/env python3
"""Remove the word 'monotherapy' from arm_name values in deployed JSON files."""

import json
import re
import sys
from pathlib import Path


def clean_arm_name(value: str) -> str:
    """Remove 'monotherapy' (and surrounding space) from arm name."""
    if not value or not isinstance(value, str):
        return value
    return re.sub(r"\s*monotherapy\s*", " ", value, flags=re.IGNORECASE).strip() or value


def process_obj(obj):
    """Recursively process dict/list and update every arm_name value."""
    if isinstance(obj, dict):
        for key, val in list(obj.items()):
            if key == "arm_name" and isinstance(val, str):
                obj[key] = clean_arm_name(val)
            else:
                process_obj(val)
    elif isinstance(obj, list):
        for item in obj:
            process_obj(item)


def main():
    data_dir = Path(__file__).resolve().parent / "data" / "deployed"
    files = [
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
    for name in files:
        path = data_dir / name
        if not path.exists():
            print(f"Skip (not found): {path}", file=sys.stderr)
            continue
        print(f"Processing {name}...")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        process_obj(data)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  Updated {name}")
    print("Done.")


if __name__ == "__main__":
    main()
