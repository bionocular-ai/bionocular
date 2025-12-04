#!/usr/bin/env python3
"""Quick test script to verify JSON files can be loaded by JSONTrialsService."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Set environment variables
os.environ["TRIALS_DATA_SOURCE"] = "json"
os.environ["TRIALS_JSON_FILES"] = (
    "data/deployed/ASCO_2020.json,"
    "data/deployed/ASCO_2021.json,"
    "data/deployed/ASCO_2022.json,"
    "data/deployed/ASCO_2023.json,"
    "data/deployed/ASCO_2024.json,"
    "data/deployed/ASCO_2025.json,"
    "data/deployed/ESMO_2020-2024.json,"
    "data/deployed/Publications_70.json"
)

from src.app.json_trials_service import JSONTrialsService


def main():
    print("🧪 Testing JSONTrialsService with deployed JSON files...")
    print()

    try:
        # Initialize service
        print("1. Initializing JSONTrialsService...")
        service = JSONTrialsService()
        print(
            f"   ✅ Service initialized with {len(service.json_file_paths)} file paths"
        )

        # Check if files exist
        print("\n2. Checking if JSON files exist...")
        missing_files = []
        for path in service.json_file_paths:
            if path.exists():
                print(f"   ✅ {path}")
            else:
                print(f"   ❌ {path} - NOT FOUND")
                missing_files.append(path)

        if missing_files:
            print(f"\n❌ {len(missing_files)} file(s) not found!")
            return 1

        # Load trials
        print("\n3. Loading trials from JSON files...")
        trials_list, total = service.get_all_trials(skip=0, limit=10)
        print(f"   ✅ Loaded {len(trials_list)} trials (showing first 10)")
        print(f"   ✅ Total trials available: {total}")

        # Check trial structure
        if trials_list:
            print("\n4. Checking trial structure...")
            sample = trials_list[0]
            required_fields = ["nct_id", "title", "phase", "sponsor", "status"]
            missing_fields = [f for f in required_fields if f not in sample]

            if missing_fields:
                print(f"   ⚠️  Missing fields: {missing_fields}")
            else:
                print("   ✅ All required fields present")
                print(
                    f"   Sample trial: {sample.get('nct_id')} - {sample.get('title', '')[:50]}..."
                )

        # Test NCT lookup
        if trials_list and trials_list[0].get("nct_id"):
            nct_id = trials_list[0]["nct_id"]
            print(f"\n5. Testing NCT lookup for {nct_id}...")
            nct_trials, nct_total = service.get_trials_by_nct_id(
                nct_id, skip=0, limit=5
            )
            print(f"   ✅ Found {nct_total} trial(s) for {nct_id}")

        print("\n✅ All tests passed!")
        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
