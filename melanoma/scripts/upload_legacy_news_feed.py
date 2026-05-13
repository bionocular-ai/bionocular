#!/usr/bin/env python3
"""One-off upload of legacy live_ticker.json data into Supabase news_feed table.

Usage:
    poetry run python3 scripts/upload_legacy_news_feed.py [--dry-run]
"""

import argparse
import json
import logging
import os
import pathlib
import sys
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("upload_legacy_news_feed")

_LEGACY_JSON = (
    pathlib.Path(__file__).parent.parent
    / "data" / "output" / "Legacy" / "live_ticker.json"
)

_CANCER_TYPE_MAP: dict[str, str] = {
    "cutaneous-melanoma": "Cutaneous Melanoma",
    "basal-cell-carcinoma": "Basal Cell Carcinoma",
    "cutaneous-squamous-cell-carcinoma": "Cutaneous Squamous Cell Carcinoma",
    "uveal-melanoma": "Uveal Melanoma",
    "merkel-cell-carcinoma": "Merkel Cell Carcinoma",
    "acral-melanoma": "Acral Melanoma",
    "mucosal-melanoma": "Mucosal Melanoma",
    "cutaneous-melanoma-with-brain-cns-metastasis": "Cutaneous Melanoma with Brain/CNS Metastasis",
}

_LEGACY_EXTRACTED_AT = "2026-01-01T00:00:00+00:00"

_SAFETY_KEYWORDS = {"safety", "adverse", "toxicity", "dlt", "trae", "grade", "ae"}
_EFFICACY_KEYWORDS = {"orr", "pfs", "dor", "dcr", "efficacy", "survival", "clearance",
                      "response", "progression", "overall"}


def _classify_efficacy_safety(metric: str) -> tuple[bool, bool]:
    """Return (has_efficacy, has_safety) from metric keyword detection."""
    lower = metric.lower()
    has_safety = any(kw in lower for kw in _SAFETY_KEYWORDS)
    has_efficacy = any(kw in lower for kw in _EFFICACY_KEYWORDS)
    if not has_safety and not has_efficacy:
        has_efficacy = True  # default: unrecognised metrics treated as efficacy
    return has_efficacy, has_safety


def parse_date(date_str: str) -> str:
    """Convert 'February 2, 2026' → '2026-02-02'."""
    return datetime.strptime(date_str, "%B %d, %Y").strftime("%Y-%m-%d")


def parse_nct_ids(nct_id: str | None) -> list[str]:
    """Convert 'NCT001, NCT002' → ['NCT001', 'NCT002']."""
    if not nct_id:
        return []
    return [n.strip() for n in nct_id.split(",") if n.strip()]


def _empty_row(url: str, title: str, date_str: str, nct_id: str | None) -> dict[str, Any]:  # values are heterogeneous (str | list | bool | dict | None)
    return {
        "url": url,
        "title": title,
        "date": parse_date(date_str),
        "cancer_type": [],
        "nct_ids": parse_nct_ids(nct_id),
        "has_efficacy": False,
        "efficacy_data": {},
        "has_safety": False,
        "safety_data": {},
        "extracted_at": None,
    }


def build_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Merge legacy JSON into one row per URL for news_feed upsert."""
    rows: dict[str, dict[str, Any]] = {}

    for slug, content in data.items():
        cancer_type = _CANCER_TYPE_MAP.get(slug)
        if cancer_type is None:
            logger.warning("Unknown slug %r — skipping (update _CANCER_TYPE_MAP if needed)", slug)
            continue

        for article in content.get("articles", []):
            url = article["url"]
            if url not in rows:
                rows[url] = _empty_row(url, article["title"], article["date"], article.get("nct_id"))
            if cancer_type not in rows[url]["cancer_type"]:
                rows[url]["cancer_type"].append(cancer_type)

        for result in content.get("results", []):
            url = result["url"]
            if url not in rows:
                rows[url] = _empty_row(url, result["title"], result["date"], result.get("nct_id"))
            if cancer_type not in rows[url]["cancer_type"]:
                rows[url]["cancer_type"].append(cancer_type)

            # Classify combined legacy field into efficacy and/or safety by keyword detection.
            eff = result.get("efficacy_or_safety_data")
            if eff and "metric" in eff:
                has_eff, has_saf = _classify_efficacy_safety(eff["metric"])
                data = {"metric": eff["metric"], "value": eff["value"]}
                if has_eff:
                    rows[url]["has_efficacy"] = True
                    rows[url]["efficacy_data"] = data
                if has_saf:
                    rows[url]["has_safety"] = True
                    rows[url]["safety_data"] = data
                rows[url]["extracted_at"] = _LEGACY_EXTRACTED_AT

    return list(rows.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print rows without writing to Supabase")
    args = parser.parse_args()

    load_dotenv()

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")

    if not args.dry_run and (not supabase_url or not supabase_key):
        logger.error("SUPABASE_URL and SUPABASE_KEY must be set (or use --dry-run)")
        return 2

    with open(_LEGACY_JSON) as f:
        data = json.load(f)

    rows = build_rows(data)
    logger.info("Built %d unique rows from legacy JSON", len(rows))

    supabase: Client | None = (
        create_client(supabase_url, supabase_key)  # type: ignore[arg-type]
        if (supabase_url and supabase_key and not args.dry_run)
        else None
    )

    counts: dict[str, int] = {"upserted": 0, "error": 0, "dry_run": 0}
    for row in rows:
        if args.dry_run:
            logger.info("[dry-run] %s | cancer_type=%s | has_efficacy=%s",
                        row["url"], row["cancer_type"], row["has_efficacy"])
            counts["dry_run"] += 1
        else:
            assert supabase is not None
            try:
                supabase.table("news_feed").upsert(row, on_conflict="url").execute()
                counts["upserted"] += 1
            except Exception as exc:
                logger.error("Upsert failed for %s: %s", row["url"], exc)
                counts["error"] += 1

    logger.info("Done: %s", counts)
    return 0 if counts["error"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
