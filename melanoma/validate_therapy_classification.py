#!/usr/bin/env python3
"""Script to validate therapy classification against actual trial data.

This script classifies all treatment arms in the database and generates
a report showing the distribution of approved vs investigational therapies.
"""

import sys
from collections import defaultdict
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.domain.therapy_classifier import TherapyClassifier


def main():
    """Validate therapy classification."""
    import json
    from pathlib import Path

    # Initialize classifier
    classifier = TherapyClassifier()

    # Load trials from JSON files directly
    print("Loading trials from JSON files...")
    base_dir = Path(__file__).parent
    json_files = [
        base_dir / "data" / "output" / "ASCO_2020.json",
        base_dir / "data" / "output" / "ASCO_2021.json",
        base_dir / "data" / "output" / "ASCO_2022.json",
        base_dir / "data" / "output" / "ASCO_2023.json",
        base_dir / "data" / "output" / "ASCO_2024.json",
        base_dir / "data" / "output" / "ASCO_2025.json",
        base_dir / "data" / "output" / "ESMO_2020-2024.json",
        base_dir / "data" / "output" / "Publications_70.json",
    ]

    trials = []
    for json_file in json_files:
        if json_file.exists():
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                    abstracts = data.get("abstracts", [])
                    publications = data.get("publications", [])
                    trials.extend(abstracts + publications)
            except Exception as e:
                print(f"Error loading {json_file.name}: {e}")

    if not trials:
        print("No trials found. Trying API...")
        import subprocess

        try:
            result = subprocess.run(
                ["curl", "-s", "http://localhost:8000/api/trials?skip=0&limit=1000"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            data = json.loads(result.stdout)
            trials = data.get("trials", [])
        except Exception as e:
            print(f"Error: {e}")
            return

    print(f"Found {len(trials)} trials\n")

    print(f"Found {len(trials)} trials\n")

    # Classify all arms
    classifications = defaultdict(int)
    arm_examples = defaultdict(list)

    for trial in trials:
        # Handle both API format and JSON file format
        if "arm_results" in trial:
            # JSON file format
            title = trial.get("abstract_id", "") or trial.get("publication_id", "")
            arm_results = trial.get("arm_results", {})
            for arm_key, arm_data in arm_results.items():
                # Try direct arm_name first
                arm_name = arm_data.get("arm_name", "")
                generic_name = arm_data.get("generic_name", "")

                # If not found, try attributes
                if not arm_name:
                    arm_attrs = arm_data.get("attributes", {})
                    arm_name_attr = arm_attrs.get(
                        "AttributeType.ARM_NAME"
                    ) or arm_attrs.get("arm_name")
                    generic_name_attr = arm_attrs.get(
                        "AttributeType.GENERIC_NAME"
                    ) or arm_attrs.get("generic_name")

                    if isinstance(arm_name_attr, dict):
                        arm_name = arm_name_attr.get("value", "")
                    elif isinstance(arm_name_attr, str):
                        arm_name = arm_name_attr

                    if isinstance(generic_name_attr, dict):
                        generic_name = generic_name_attr.get("value", "")
                    elif isinstance(generic_name_attr, str):
                        generic_name = generic_name_attr

                if not arm_name:
                    continue

                status = classifier.classify_arm(arm_name, generic_name, title)
                classifications[status.value] += 1

                if len(arm_examples[status.value]) < 5:
                    arm_examples[status.value].append(
                        {
                            "arm_name": arm_name,
                            "generic_name": generic_name,
                            "trial_title": title[:80] + "..."
                            if len(title) > 80
                            else title,
                        }
                    )
        else:
            # API format
            title = trial.get("title", "")
            arms = trial.get("arms", [])

            for arm in arms:
                arm_name = arm.get("arm_name", "")
                generic_name = arm.get("generic_name", "")

                if not arm_name:
                    continue

                status = classifier.classify_arm(arm_name, generic_name, title)
                classifications[status.value] += 1

                if len(arm_examples[status.value]) < 5:
                    arm_examples[status.value].append(
                        {
                            "arm_name": arm_name,
                            "generic_name": generic_name,
                            "trial_title": title[:80] + "..."
                            if len(title) > 80
                            else title,
                        }
                    )

    # Print report
    print("=" * 80)
    print("THERAPY CLASSIFICATION REPORT")
    print("=" * 80)
    print()

    total_arms = sum(classifications.values())
    print(f"Total arms classified: {total_arms}\n")

    for status in ["approved", "investigational", "control", "unknown"]:
        count = classifications.get(status, 0)
        percentage = (count / total_arms * 100) if total_arms > 0 else 0
        print(f"{status.upper()}: {count} ({percentage:.1f}%)")

        if arm_examples.get(status):
            print("  Examples:")
            for example in arm_examples[status]:
                print(f"    - {example['arm_name']}")
                if example["generic_name"]:
                    print(f"      Generic: {example['generic_name']}")
            print()

    # Detailed breakdown by agent
    print("\n" + "=" * 80)
    print("AGENT FREQUENCY ANALYSIS")
    print("=" * 80)
    print()

    agent_counts = defaultdict(
        lambda: {"approved": 0, "investigational": 0, "control": 0, "unknown": 0}
    )

    # Simplified agent counting - skip for now to avoid complexity
    # This section can be enhanced later

    # Print top agents
    print("Top agents by frequency:")
    sorted_agents = sorted(
        agent_counts.items(), key=lambda x: sum(x[1].values()), reverse=True
    )[:20]

    for agent, counts in sorted_agents:
        total = sum(counts.values())
        if total > 0:
            print(f"\n{agent}: {total} occurrences")
            for status, count in counts.items():
                if count > 0:
                    print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
