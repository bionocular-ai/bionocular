#!/usr/bin/env python3
"""Export selected ClinicalTrials.gov API fields from clinical_trials_cache to text files.

Reads each trial from clinical_trials_cache, extracts:
  - NCT (identificationModule.nctId)
  - officialTitle (identificationModule.officialTitle)
  - first entry from armsInterventionsModule: armGroups[0] if present, else interventions[0]
  - Inclusion Criteria (eligibilityModule.eligibilityCriteria, inclusion section only)

and writes one text file per trial named {NCT_ID}.txt (e.g. NCT01234567.txt).

Option --industry-only: only export trials whose lead sponsor is Industry
(protocolSection.sponsorCollaboratorsModule.leadSponsor.class == "INDUSTRY").

With --index, also writes _index.txt: one line per trial (NCT, briefTitle, keywords)
for use in NotebookLM/Gemini as a single searchable overview (see GEMINI_NOTEBOOKLM.md).

Usage:
  cd melanoma
  poetry run python export_clinical_trial_api_fields.py --industry-only
  poetry run python export_clinical_trial_api_fields.py --index --out-dir data/trials_db/trial_api_exports
"""

import argparse
import json
import logging
import re
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "trials_db" / "trials.db"
DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "data" / "trials_db" / "trial_api_exports"

NCT_PATTERN = re.compile(r"^NCT\d+$", re.IGNORECASE)


def parse_inclusion_criteria(eligibility_criteria: str | None) -> str:
    """Extract only the inclusion criteria section from eligibilityModule.eligibilityCriteria.

    Cuts at "Exclusion Criteria:" or "Key Exclusion Criteria:" (case-insensitive).
    Keeps the inclusion block including headers like "Key Inclusion Criteria:" or
    "Inclusion Criteria:" and any subsections (e.g. "Additional key inclusion criterion...").
    """
    if not eligibility_criteria or not eligibility_criteria.strip():
        return ""
    text = eligibility_criteria.strip()
    # Cut at Exclusion (with optional "Key " prefix)
    exclusion_marker = re.compile(r"\n\s*(Key\s+)?Exclusion Criteria\s*:", re.IGNORECASE)
    match = exclusion_marker.search(text)
    if match is not None:
        text = text[: match.start()].strip()
    # Optionally trim any preamble before the first Inclusion section
    incl_start = re.compile(r"(Key\s+)?Inclusion Criteria\s*:", re.IGNORECASE)
    incl_match = incl_start.search(text)
    if incl_match is not None:
        text = text[incl_match.start() :].strip()
    return text


def parse_first_criteria_section(eligibility_criteria: str | None) -> str:
    """When eligibility has no 'Inclusion Criteria:', return the first section that mentions 'criteria'.

    Cuts at Exclusion if present, then finds the first line containing 'criteria'
    (e.g. 'Eligibility Criteria:', 'Key Criteria:') and returns from that line to end of block.
    """
    if not eligibility_criteria or not eligibility_criteria.strip():
        return ""
    text = eligibility_criteria.strip()
    # Cut at Exclusion (with optional "Key " prefix)
    exclusion_marker = re.compile(r"\n\s*(Key\s+)?Exclusion Criteria\s*:", re.IGNORECASE)
    match = exclusion_marker.search(text)
    if match is not None:
        text = text[: match.start()].strip()
    if not text or "criteria" not in text.lower():
        return ""
    # Find first line that contains "criteria"; start output from the start of that line
    criteria_line = re.compile(r"(^|\n)([^\n]*\bcriteria\b[^\n]*)", re.IGNORECASE)
    m = criteria_line.search(text)
    if m is None:
        return ""
    return text[m.start(2) :].strip()


def extract_fields(api_response_json: dict) -> dict:
    """Extract the requested API fields from a full API response."""
    protocol = api_response_json.get("protocolSection", {})
    id_module = protocol.get("identificationModule", {})
    arms_interventions = protocol.get("armsInterventionsModule", {})
    eligibility_module = protocol.get("eligibilityModule", {})

    arm_groups = arms_interventions.get("armGroups") or []
    interventions = arms_interventions.get("interventions") or []
    # First entry from module: prefer first armGroup, else first intervention (not all trials have armGroups)
    first_arm_or_intervention = (
        arm_groups[0] if arm_groups else (interventions[0] if interventions else None)
    )

    eligibility_criteria = eligibility_module.get("eligibilityCriteria") or ""
    if "inclusion criteria:" in eligibility_criteria.lower():
        inclusion_criteria = parse_inclusion_criteria(eligibility_criteria)
    elif "criteria" in eligibility_criteria.lower():
        inclusion_criteria = parse_first_criteria_section(eligibility_criteria)
    else:
        inclusion_criteria = ""

    sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
    lead_sponsor = sponsor_module.get("leadSponsor", {})
    sponsor_class = lead_sponsor.get("class") or ""
    is_industry = sponsor_class == "INDUSTRY"

    return {
        "nct_number": id_module.get("nctId"),
        "officialTitle": id_module.get("officialTitle"),
        "first_arm_or_intervention": first_arm_or_intervention,
        "inclusion_criteria": inclusion_criteria,
        "is_industry_sponsor": is_industry,
        # Keep for --index
        "briefTitle": id_module.get("briefTitle"),
        "keywords": protocol.get("conditionsModule", {}).get("keywords") or [],
    }


def format_value(value):  # noqa: ANN201
    """Format a value for human-readable text output."""
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, indent=2, ensure_ascii=False)
    return str(value)


def write_trial_file(out_path: Path, fields: dict) -> None:
    """Write one trial's extracted fields to a text file."""
    lines = [
        "NCT Number: " + (fields.get("nct_number") or ""),
        "",
        "officialTitle:",
        format_value(fields.get("officialTitle")) or "(empty)",
        "",
        "firstArmOrIntervention:",
        format_value(fields.get("first_arm_or_intervention")) or "(none)",
        "",
        format_value(fields.get("inclusion_criteria")) or "(empty)",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export selected ClinicalTrials.gov API fields from clinical_trials_cache to text files (one per NCT)."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to trials SQLite database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Directory to write text files (default: {DEFAULT_OUT_DIR})",
    )
    parser.add_argument(
        "--index",
        action="store_true",
        help="Also write _index.txt for Gemini/NotebookLM overview",
    )
    parser.add_argument(
        "--index-style",
        choices=["minimal", "full"],
        default="minimal",
        help="minimal = NCT + briefTitle only (~500KB). full = + keywords (~1MB). Default: minimal.",
    )
    parser.add_argument(
        "--industry-only",
        action="store_true",
        help="Only export trials whose lead sponsor is Industry (leadSponsor.class == INDUSTRY).",
    )
    args = parser.parse_args()

    if not args.db_path.exists():
        logger.error("Database not found: %s", args.db_path)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)

    try:
        conn = sqlite3.connect(str(args.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT nct_number, api_response_json FROM clinical_trials_cache"
        )
        rows = cursor.fetchall()
        conn.close()
    except sqlite3.Error as e:
        logger.error("Database error: %s", e)
        return 1

    if not rows:
        logger.warning("No rows in clinical_trials_cache. Nothing to export.")
        return 0

    all_fields: list[dict] = []
    written = 0
    exported_ncts: set[str] = set()
    for nct_number, api_response_text in rows:
        try:
            api_response = json.loads(api_response_text)
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON for %s: %s", nct_number, e)
            continue

        fields = extract_fields(api_response)
        # Use NCT from row in case it's missing in JSON
        fields["nct_number"] = fields.get("nct_number") or nct_number
        nct = fields["nct_number"]
        if not nct:
            logger.warning("Skipping row with no NCT number")
            continue

        if args.industry_only and not fields.get("is_industry_sponsor"):
            continue

        out_path = args.out_dir / f"{nct}.txt"
        write_trial_file(out_path, fields)
        written += 1
        exported_ncts.add(nct)
        if args.index:
            all_fields.append(fields)

    if args.index and all_fields:
        all_fields.sort(key=lambda f: (f.get("nct_number") or ""))
        if args.index_style == "minimal":
            index_lines = [
                "NCT\tbriefTitle",
                *(
                    "\t".join(
                        [
                            (f.get("nct_number") or ""),
                            (f.get("briefTitle") or "").replace("\t", " ").replace("\n", " "),
                        ]
                    )
                    for f in all_fields
                ),
            ]
        else:
            index_lines = [
                "NCT\tbriefTitle\tkeywords",
                *(
                    "\t".join(
                        [
                            (f.get("nct_number") or ""),
                            (f.get("briefTitle") or "").replace("\t", " ").replace("\n", " "),
                            ",".join(f.get("keywords") or []),
                        ]
                    )
                    for f in all_fields
                ),
            ]
        index_path = args.out_dir / "_index.txt"
        index_path.write_text("\n".join(index_lines), encoding="utf-8")
        logger.info("Wrote index %s (%d trials, %s)", index_path, len(all_fields), args.index_style)

    # Remove trial files in out_dir that were not exported this run (e.g. no "Inclusion Criteria:", or non-Industry when --industry-only)
    if exported_ncts:
        removed = 0
        for path in args.out_dir.iterdir():
            if path.is_file() and path.suffix == ".txt" and path.stem != "_index":
                if NCT_PATTERN.match(path.stem) and path.stem not in exported_ncts:
                    path.unlink()
                    removed += 1
        if removed:
            logger.info("Removed %d trial files not matching current filters from %s", removed, args.out_dir)

    logger.info("Wrote %d trial files to %s", written, args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
