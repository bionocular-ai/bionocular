#!/usr/bin/env python3
"""Export selected ClinicalTrials.gov API fields from clinical_trials_cache to text files.

Reads each trial from clinical_trials_cache, extracts:
  - NCT (identificationModule.nctId)
  - officialTitle (identificationModule.officialTitle)
  - briefSummary (descriptionModule.briefSummary)
  - eligibilityCriteria (eligibilityModule.eligibilityCriteria, full text)

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

# Section header that starts the block we strip from eligibilityCriteria
_PATIENT_CHARACTERISTICS_START = re.compile(
    r"\n\s*PATIENT\s+CHARACTERISTICS\s*:|\n\s*--\s*Patient\s+Characteristics\s*--",
    re.IGNORECASE,
)
# Next section headers (all-caps with colon, or --Name--); used as end boundary
_NEXT_SECTION_AFTER_PATIENT = re.compile(
    r"\n\s*(?:PRIOR\s+CONCURRENT\s+THERAPY|DISEASE\s+CHARACTERISTICS|PROTOCOL\s+ENTRY\s+CRITERIA)\s*:"
    r"|\n\s*--\s*[A-Za-z/\s]+\s*--",
    re.IGNORECASE,
)

# Exclusion-criteria section headers (all variants) — we strip these blocks from eligibility
_EXCLUSION_SECTION_START = re.compile(
    r"\n\s*EXCLUSION\s+CRITERIA\s*(?:\s+for\s+[^:\n]+)?\s*:"
    r"|\n\s*EXCLUSION\s+CRITERIA\s*[\-\s]"  # e.g. "EXCLUSION CRITERIA - Patients meeting..."
    r"|\n\s*CELL\s+INFUSION\s+EXCLUSION\s+CRITERIA\s*:"
    r"|\n\s*\\?\[Exclusion\s+Criteria\s+[^\]]*\]"  # "[Exclusion Criteria (Phase 1 and Phase 2)]" or \[...\]
    r"|\n\s*Tissue\s+Procurement\s+Exclusion\s+Criteria\s*:"
    r"|\n\s*Study\s+Enrollment\s+Exclusion\s+Criteria\s*:"
    r"|\n\s*Key\s+Exclusion\s+Criteria\s*(?:\s*\([^)]*\))?\s*:?\s*\n?"  # with or without (Phase...), (both parts), (applicable...)
    r"|\n\s*Key\s+exclusion\s+criteria\s+common\s+to\s+[^\n]*:"
    r"|\n\s*Exclusion\s+Criteria\s*[\-\:]"  # "Exclusion Criteria - Key criteria include:" or "...:"
    r"|\n\s*Exclusion\s+Criteria\s*\("  # "Exclusion Criteria (Potential...", "(Summary):", "(Parts B & C):", "'Normals':"
    r"|\n\s*Exclusion\s+Criteria\s*\'[^\']*\'"  # "Exclusion Criteria 'Normals':"
    r"|\n\s*Exclusion\s+Criteria\s+Part\s+[A-Za-z]\s*\n"  # "Exclusion Criteria Part A" / "Part B"
    r"|\n\s*Exclusion\s+Criteria\s*\.\s*\n"  # "Exclusion Criteria."
    r"|\n\s*Exclusion\s+Criteria\s*\.\s+Patients\s+who\s+meet"  # "Exclusion Criteria. Patients who meet any of the criteria below..."
    r"|\n\s*Exclusion\s+Criteria\s*\n"
    r"|\n\s*Exclusion\s+Criteria\s*[\:\：]\s*\n?"  # "Exclusion Criteria:" or fullwidth colon
    r"|\n\s*Exclusion\s*:\s*\n"  # "Exclusion:" on its own line
    r"|\n\s*Exclusion\s+criteria\s*\.\s+Subjects\s+who\s+fulfill"  # "Exclusion criteria. Subjects who fulfill..."
    r"|\n\s*Exclusion\s*\n"
    r"|\n\s*Patients\s+meeting\s+[^\n]*exclusion\s+criteria[^\n]*:"  # "Patients meeting any one of these exclusion criteria will be prohibited..."
    r"|\n\s*Primary\s+exclusion\s+criteria\s*:"
    r"|\n\s*Main\s+exclusion\s+criteria\s+include\s*:"
    r"|\n\s*Main\s+Exclusion\s+Criteria\s*(?:\s+for\s+[^\n]*)?\s*:?\s*\n?"  # "Main Exclusion Criteria:", "Main Exclusion Criteria", "Main Exclusion Criteria for patients..."
    r"|\n\s*Main\s+exclusion\s+criteria\s+(?:Cohort\s+\d+\s*:)?\s*\n?"  # "Main exclusion criteria", "Main exclusion criteria Cohort 1:"
    r"|\n\s*Additional\s+exclusion\s+criteria\s+for\s+[^\n]*:"  # "Additional exclusion criteria for the triple combinations:"
    r"|\n\s*Criteria\s+for\s+Exclusion\s*:"  # "Criteria for Exclusion:"
    r"|\n\s*\d+\.\d+\s+Exclusion\s+Criteria\s*\n?"  # "4.2 Exclusion Criteria" (numbered section)
    r"|\n\s*General\s+Exclusion\s+Criteria\s*[\:\s\(]"  # "General Exclusion Criteria:", "(All patients...)"
    r"|\n\s*Part\s+[A-Za-z]+-specific\s+Exclusion\s+Criteria\s*:"  # "Part A-specific Exclusion Criteria:"
    r"|\n\s*Select\s+Exclusion\s+Criteria\s*:"
    r"|\n\s*Partial\s+Exclusion\s+Criteria\s*:"
    r"|\n\s*Monotherapy\s+Exclusion\s+Criteria\s*\("  # "Monotherapy Exclusion Criteria (Parts A and B)"
    r"|\n\s*Combination\s+Exclusion\s+Criteria\s*\("  # "Combination Exclusion Criteria (Part C/D)"
    r"|\n\s*Abbreviated\s+Exclusion\s+Criteria\s*:"
    r"|\n\s*Prospective\s+Exclusion\s+Criteria\s*:"
    r"|\n\s*Control\s+Arm\s+Exclusion\s+Criteria\s*:"
    r"|\n\s*Diagnosis\s+and\s+main\s+criteria\s+for\s+inclusion\s+and\s+exclusion\s*:"
    r"|\n\s*The\s+following\s+are\s+the\s+main\s+exclusion\s+criteria\s*:"
    r"|\n\s*Part\s+\d+\s*:\s*Key\s+Exclusion\s+Criteria\s*\n?"  # "Part 1: Key Exclusion Criteria"
    r"|\n\s*[A-Za-z]+-specific\s+exclusion\s+criteria\s*:"  # "Melanoma-specific exclusion criteria:", "SCCHN-specific..."
    r"|\n\s*Parts\s+[A-Za-z,\s]+\s+Exclusion\s+Criteria\s*:"  # "Parts A, B, C and D Exclusion Criteria:"
    r"|\n\s*Phase\s+\d+\s+and\s+\d+\s+Exclusion\s+Criteria\s*:"  # "Phase 1 and 2 Exclusion Criteria:"
    r"|\n\s*Recent\s+medical\s+concerns\s+exclusions\s*:"
    r"|\n\s*Medical\s+Exclusion\s+Criteria\s*:"
    r"|\n\s*Common\s+exclusion\s+criteria\s+"  # "Common exclusion criteria to Dose escalation..."
    r"|\n\s*For\s+[^\n]*additional\s+exclusion\s+criteria\s+are\s*:",  # "For the HNSCC... additional exclusion criteria are:"
    re.IGNORECASE,
)


def _strip_patient_characteristics_section(text: str) -> str:
    """Remove the PATIENT CHARACTERISTICS / --Patient Characteristics-- block from eligibility text."""
    if not text or not text.strip():
        return text
    result = text
    start_match = _PATIENT_CHARACTERISTICS_START.search(result)
    while start_match:
        start_pos = start_match.start()
        rest = result[start_match.end() :]
        end_match = _NEXT_SECTION_AFTER_PATIENT.search(rest)
        end_offset = end_match.start() if end_match else len(rest)
        section_end = start_match.end() + end_offset
        result = result[:start_pos] + result[section_end:]
        result = re.sub(r"\n{3,}", "\n\n", result)
        start_match = _PATIENT_CHARACTERISTICS_START.search(result)
    return result.strip()


def _strip_exclusion_criteria_sections(text: str) -> str:
    """Remove EXCLUSION CRITERIA / Exclusion / CELL INFUSION EXCLUSION CRITERIA blocks from eligibility text."""
    if not text or not text.strip():
        return text
    result = text
    start_match = _EXCLUSION_SECTION_START.search(result)
    while start_match:
        start_pos = start_match.start()
        rest = result[start_match.end() :]
        # End of block: next exclusion section or end of string
        next_match = _EXCLUSION_SECTION_START.search(rest)
        end_offset = next_match.start() if next_match else len(rest)
        section_end = start_match.end() + end_offset
        result = result[:start_pos] + result[section_end:]
        result = re.sub(r"\n{3,}", "\n\n", result)
        start_match = _EXCLUSION_SECTION_START.search(result)
    return result.strip()


def extract_fields(api_response_json: dict) -> dict:
    """Extract the requested API fields from a full API response."""
    protocol = api_response_json.get("protocolSection", {})
    id_module = protocol.get("identificationModule", {})
    description_module = protocol.get("descriptionModule", {})
    eligibility_module = protocol.get("eligibilityModule", {})

    eligibility_criteria = _strip_patient_characteristics_section(
        eligibility_module.get("eligibilityCriteria") or ""
    )
    eligibility_criteria = _strip_exclusion_criteria_sections(eligibility_criteria)

    sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
    lead_sponsor = sponsor_module.get("leadSponsor", {})
    sponsor_class = lead_sponsor.get("class") or ""
    is_industry = sponsor_class == "INDUSTRY"

    return {
        "nct_number": id_module.get("nctId"),
        "officialTitle": id_module.get("officialTitle"),
        "briefSummary": description_module.get("briefSummary"),
        "eligibilityCriteria": eligibility_criteria,
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
        "briefSummary:",
        format_value(fields.get("briefSummary")) or "(empty)",
        "",
        "eligibilityCriteria:",
        format_value(fields.get("eligibilityCriteria")) or "(empty)",
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

    # Remove trial files in out_dir that were not exported this run (e.g. non-Industry when --industry-only)
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
