#!/usr/bin/env python3
"""
Parse number_of_patients_first_half.txt and number_of_patients_second_half.txt,
and update number_of_patients in Publications_70.json for each arm.
Only updates publications where the arm count in the text files exactly matches
the JSON (skips mismatches). When arm count matches, replaces the value for each
appropriate arm (matched by arm name when possible, else by position).
"""
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data" / "deployed"
PUB_JSON = DATA_DIR / "Publications_70.json"
FIRST_HALF = DATA_DIR / "number_of_patients_first_half.txt"
SECOND_HALF = DATA_DIR / "number_of_patients_second_half.txt"


def extract_number(s: str) -> int | None:
    """Extract first integer from strings like '403', '87 treated', '36 (35 treated),'."""
    s = s.strip().rstrip(",")
    m = re.match(r"^(\d+)", s)
    return int(m.group(1)) if m else None


def parse_first_half(content: str) -> dict[str, list[tuple[str, int]]]:
    """Parse first half file. Returns pub_id -> [(arm_name, count), ...] in order."""
    result: dict[str, list[tuple[str, int]]] = {}
    lines = content.splitlines()
    current_pub: str | None = None
    for line in lines:
        if not line.strip() or line.startswith("Based on") or "Number of Patients" in line or ("PDF Name" in line and "\t" in line and "NCT" in line):
            continue
        parts = line.split("\t")
        if len(parts) >= 4 and parts[0].strip().endswith(".pdf"):
            current_pub = parts[0].strip().removesuffix(".pdf")
            arm_name = parts[2].strip() if len(parts) > 2 else ""
            num = extract_number(parts[-1])
            if current_pub and num is not None:
                result.setdefault(current_pub, []).append((arm_name, num))
            continue
        if current_pub and len(parts) >= 3:
            arm_name = parts[2].strip() if parts[2].strip() else (parts[1].strip() if parts[1].strip() else "")
            last = parts[-1].strip()
            if last:
                num = extract_number(last)
                if num is not None and arm_name:
                    result.setdefault(current_pub, []).append((arm_name, num))
    return result


def parse_second_half(content: str) -> dict[str, list[tuple[str, int]]]:
    """Parse second half file. Returns pub_id -> [(arm_name, count), ...] in order."""
    result: dict[str, list[tuple[str, int]]] = {}
    lines = content.splitlines()
    current_pub: str | None = None
    for line in lines:
        if not line.strip() or line.startswith("Based on") or "Number of Patients" in line or ("PDF Name" in line and "Treatment" in line) or ("Treatment Arm" in line and "Extraction" in line):
            continue
        if "NCT Unique Identifier" in line or ("PDF Name" in line and "Trial" in line):
            continue
        parts = line.split("\t")
        if len(parts) >= 4 and parts[0].strip().endswith(".pdf"):
            current_pub = parts[0].strip().removesuffix(".pdf")
            arm_name = parts[2].strip() if len(parts) > 2 else ""
            num = extract_number(parts[-1])
            if current_pub and num is not None:
                result.setdefault(current_pub, []).append((arm_name, num))
            continue
        if current_pub and len(parts) >= 3:
            arm_name = parts[2].strip() if parts[2].strip() else (parts[1].strip() if parts[1].strip() else "")
            last = parts[-1].strip()
            if last:
                num = extract_number(last)
                if num is not None and arm_name:
                    result.setdefault(current_pub, []).append((arm_name, num))
    return result


def _normalize_arm_name(s: str) -> str:
    """Lowercase, collapse spaces, and normalize for fuzzy matching (dosage, plus/+, etc.)."""
    s = " ".join(s.lower().split())
    # Collapse "N mg" / "N kg" to "Nmg" / "Nkg" so "350 mg" matches "350mg", "3 mg/kg" matches "3mg/kg"
    s = re.sub(r"(\d)\s+(mg|kg)", r"\1\2", s, flags=re.IGNORECASE)
    # Normalize "plus" to "+" so "Neoadjuvant plus Adjuvant" matches "Neoadjuvant + Adjuvant"
    s = re.sub(r"\bplus\b", "+", s)
    return s


# Attribute keys used for number_of_patients in the JSON (some pubs use one, some the other)
NUMBER_OF_PATIENTS_KEYS = ("number_of_patients", "AttributeType.NUMBER_OF_PATIENTS")


def main() -> None:
    first_content = FIRST_HALF.read_text()
    second_content = SECOND_HALF.read_text()

    first_data = parse_first_half(first_content)
    second_data = parse_second_half(second_content)

    # Merge: second half may override or add; same pub_id should not appear in both
    merged: dict[str, list[tuple[str, int]]] = {**first_data, **second_data}

    total_arms_in_txt = sum(len(v) for v in merged.values())
    print(f"Arms in first half file: {sum(len(v) for v in first_data.values())}")
    print(f"Arms in second half file: {sum(len(v) for v in second_data.values())}")
    print(f"Total arms in text files (merged): {total_arms_in_txt}")
    print(f"Publications in text files: {len(merged)}")

    with open(PUB_JSON) as f:
        data = json.load(f)

    json_total_arms = data.get("total_arms", 0)
    json_publications = data.get("publications", [])
    print(f"Publications_70.json total_arms: {json_total_arms}")
    print(f"Publications_70.json publications: {len(json_publications)}")

    if total_arms_in_txt != json_total_arms:
        print(f"\nWARNING: Arm count mismatch. Text files have {total_arms_in_txt} arms, JSON has {json_total_arms} arms.")
        json_pub_ids = {p["publication_id"] for p in json_publications}
        txt_pub_ids = set(merged.keys())
        only_json = json_pub_ids - txt_pub_ids
        only_txt = txt_pub_ids - json_pub_ids
        if only_json:
            print(f"  In JSON only: {sorted(only_json)}")
        if only_txt:
            print(f"  In text only: {sorted(only_txt)}")
    else:
        print("\nArm count matches: text files contain exactly the same number of arms as the JSON (131).")

    # Only update publications where arm count matches exactly; then replace number_of_patients for each arm
    updates = 0
    skipped_mismatch: list[str] = []
    for pub in json_publications:
        pub_id = pub["publication_id"]
        arm_results = pub.get("arm_results") or {}
        arm_ids = sorted(arm_results.keys(), key=lambda x: int(x.split("_")[1]) if "_" in x else 0)
        txt_arms = merged.get(pub_id)  # list of (arm_name, count)
        if not txt_arms:
            continue
        if len(txt_arms) != len(arm_ids):
            skipped_mismatch.append(f"{pub_id} (text={len(txt_arms)} vs JSON={len(arm_ids)})")
            continue
        # Build txt lookup: exact arm name -> count, and normalized arm name -> count
        txt_by_name: dict[str, int] = {}
        txt_by_norm: dict[str, int] = {}
        for arm_name, count in txt_arms:
            txt_by_name[arm_name] = count
            txt_by_norm[_normalize_arm_name(arm_name)] = count
        # Update each JSON arm with the appropriate count (match by name, else by position)
        for i, arm_id in enumerate(arm_ids):
            if i >= len(txt_arms):
                break
            arm = arm_results[arm_id]
            json_arm_name = (arm.get("arm_name") or "").strip()
            attrs = arm.get("attributes") or {}
            nop = None
            for key in NUMBER_OF_PATIENTS_KEYS:
                if key in attrs:
                    nop = attrs[key]
                    break
            if nop is None:
                continue
            new_val = (
                txt_by_name.get(json_arm_name)
                or txt_by_norm.get(_normalize_arm_name(json_arm_name))
                or txt_arms[i][1]
            )
            old_val = nop.get("value")
            nop["value"] = new_val
            nop["confidence"] = 0.9
            nop["source"] = "manual_entry"
            updates += 1
            if old_val != new_val:
                print(f"  {pub_id} {arm_id} ({json_arm_name!r}): number_of_patients {old_val} -> {new_val}")

    if skipped_mismatch:
        print(f"\nSkipped (arm count mismatch): {', '.join(skipped_mismatch)}")
    print(f"\nTotal number_of_patients updated: {updates}")

    with open(PUB_JSON, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Wrote {PUB_JSON}")


if __name__ == "__main__":
    main()
