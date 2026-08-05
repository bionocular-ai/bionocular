"""
Delete all source_type='publication' rows from trial_outcomes, then insert
fresh rows from a publications extraction JSON.

Usage:
    cd melanoma
    poetry run python3 scripts/replace_publications_supabase.py [--dry-run] [--file PATH]
"""

import argparse
import json
import os
import pathlib
import re
import sys

from dotenv import load_dotenv

# Load env BEFORE importing upload_to_supabase — that module sys.exits if env missing
load_dotenv()

_here = pathlib.Path(__file__).parent
_root = _here.parent
sys.path.insert(0, str(_root))    # melanoma/ → enables `from src...`
sys.path.insert(0, str(_here))    # scripts/  → enables `from upload_to_supabase import ...`

from upload_to_supabase import ATTRIBUTE_MAPPING  # noqa: E402
from src.infrastructure.clinical_trials.supabase_parser import normalize_cancer_type  # noqa: E402

from supabase import Client, create_client  # noqa: E402

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
if not url or not key:
    print("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    sys.exit(1)

supabase: Client = create_client(url, key)

DEFAULT_JSON = str(
    _root / "data/output/Publication_May_2026/extraction_results_Publications_final_70.json"
)

EMPTY_VALUES = {None, "", "Not found", "N/A", "Not available", "Not reached"}


def parse_numeric(val: str) -> tuple[float | None, bool]:
    """Parse a numeric string, falling back to the value inside parentheses.

    Handles dirty extraction outputs like '1 (<1%)' or '<1' by extracting
    the parenthesized portion first, then stripping <, >, % characters.

    Returns (value, is_censored). A censored value like '<1' stores its bound as
    the number so it still plots; the caller records the column in is_lt so the
    '<' is not lost.
    """
    try:
        return float(val), False
    except (ValueError, TypeError):
        pass
    m = re.search(r'\(([^)]+)\)', val)
    candidate = m.group(1) if m else val
    censored = "<" in candidate
    stripped = re.sub(r'[<>%]', '', candidate).strip()
    try:
        return float(stripped), censored
    except (ValueError, TypeError):
        return None, False


def build_rows(publications: list) -> list[dict]:
    rows = []
    for pub in publications:
        pub_id = pub.get("pub_id", "unknown")
        arm_results = pub.get("arm_results", {})
        if not arm_results:
            continue

        first_arm_attrs = next(iter(arm_results.values()), {}).get("attributes", {})

        # Normalize all attribute keys once for this pub
        def _norm(attrs: dict) -> dict:
            return {
                k.lower().replace("attributetype.", "").replace("_", ""): v
                for k, v in attrs.items()
            }

        first_norm = _norm(first_arm_attrs)

        # publication_id = publication_name attribute of first arm
        pub_name_obj = first_norm.get("publicationname", {})
        pub_name = pub_name_obj.get("value")
        publication_id = None if pub_name in EMPTY_VALUES else pub_name

        # nct_id from attribute
        nct_obj = first_norm.get("nctnumber", {}) or first_norm.get("nctid", {})
        nct_raw = nct_obj.get("value")
        nct_id = None if nct_raw in EMPTY_VALUES else nct_raw

        for arm_key, arm_data in arm_results.items():
            arm_id = arm_data.get("arm_id", arm_key)
            attrs = arm_data.get("attributes", {})
            norm_attrs = _norm(attrs)

            pk = f"publication_{pub_id}_{arm_id}".replace("/", "_").replace(" ", "_")

            record: dict = {
                "id": pk,
                "source_type": "publication",
                "source_name": pub_id,
                "abstract_id": None,
                "publication_id": publication_id,
                "source_url": None,
                "nct_id": nct_id,
                "arm_id": arm_id,
                "arm_name": arm_data.get("arm_name"),
                "confidence": pub.get("overall_confidence", 0.0),
            }

            known_strings = {
                "id", "source_type", "source_name", "abstract_id", "publication_id",
                "source_url", "nct_id", "arm_id", "arm_name", "cancer_type", "sponsors",
                "line_of_treatment", "generic_name", "brand_name", "dosage",
                "type_of_dosing", "mechanism_of_action", "target_protein",
                "type_of_therapy", "sub_therapy", "is_nr", "is_lt", "all_attributes",
                "created_at", "ci_hr_pfs", "ci_hr_os", "ci_hr_efs",
                "ci_hr_rfs", "ci_hr_mfs", "ci_hr_ttp",
            }

            is_nr_list: list[str] = []
            is_lt_list: list[str] = []
            for attr_key, col_name in ATTRIBUTE_MAPPING.items():
                is_num = col_name not in known_strings
                clean_target = attr_key.lower().replace("_", "")
                val_obj = norm_attrs.get(clean_target, {})
                val = val_obj.get("value")

                if str(val).upper() in {"NR", "NOT REACHED", "NOTREACHED"}:
                    is_nr_list.append(col_name)
                    val = None
                elif val in EMPTY_VALUES:
                    val = None

                if is_num and val is not None:
                    val, censored = parse_numeric(val)
                    if censored:
                        is_lt_list.append(col_name)
                    if val is not None and col_name == "num_patients":
                        val = int(val)

                record[col_name] = val

            # Fallback num_patients from arm-level field
            if record.get("num_patients") is None:
                arm_pc = arm_data.get("patient_count")
                if isinstance(arm_pc, (int, float)) and arm_pc > 0:
                    record["num_patients"] = int(arm_pc)

            # Publications JSON stores these under different keys than ATTRIBUTE_MAPPING expects:
            #   generic_name / dose / dosing_schedule → arm-level fields (not in attributes)
            #   target        → target_protein
            #   modality      → type_of_therapy
            def _arm_str(field: str) -> str | None:
                v = arm_data.get(field)
                return v if v and v not in EMPTY_VALUES else None

            def _attr_str(key: str) -> str | None:
                v = norm_attrs.get(key, {}).get("value")
                return v if v and v not in EMPTY_VALUES else None

            if record.get("generic_name") is None:
                record["generic_name"] = _arm_str("generic_name")
            if record.get("dosage") is None:
                record["dosage"] = _arm_str("dose")
            if record.get("type_of_dosing") is None:
                record["type_of_dosing"] = _arm_str("dosing_schedule")
            if record.get("target_protein") is None:
                record["target_protein"] = _attr_str("target")
            record["modality"] = _attr_str("modality")

            # cancer_type → TEXT[]
            raw_ct = record.get("cancer_type")
            if isinstance(raw_ct, str):
                record["cancer_type"] = normalize_cancer_type(raw_ct)
            elif not isinstance(raw_ct, list):
                record["cancer_type"] = []

            record["is_nr"] = is_nr_list if is_nr_list else None
            record["is_lt"] = is_lt_list if is_lt_list else None
            rows.append(record)

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Replace publication rows in trial_outcomes")
    parser.add_argument("--dry-run", action="store_true", help="Transform only, skip DB writes")
    parser.add_argument("--file", default=DEFAULT_JSON, help="Path to publications JSON")
    args = parser.parse_args()

    json_path = pathlib.Path(args.file)
    if not json_path.exists():
        print(f"File not found: {json_path}")
        sys.exit(1)

    with open(json_path) as f:
        data = json.load(f)

    publications = data.get("publications", [])
    print(f"Loaded {len(publications)} publications from {json_path.name}")

    rows = build_rows(publications)
    print(f"Transformed {len(rows)} arms")

    if args.dry_run:
        print("[dry-run] Skipping delete and upsert.")
        return

    # Step 1: delete existing publication rows
    supabase.table("trial_outcomes").delete().eq("source_type", "publication").execute()
    print("Deleted existing publication rows from trial_outcomes")

    # Step 2: upsert in batches of 50
    batch_size = 50
    total_batches = (len(rows) + batch_size - 1) // batch_size
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        batch_num = i // batch_size + 1
        try:
            supabase.table("trial_outcomes").upsert(batch).execute()
            print(f"  ✓ Batch {batch_num}/{total_batches}")
        except Exception as e:
            print(f"  ✗ Batch {batch_num}/{total_batches} failed: {e}")

    print(f"Done. {len(rows)} rows inserted into trial_outcomes.")


if __name__ == "__main__":
    main()
