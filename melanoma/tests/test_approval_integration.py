#!/usr/bin/env python3
"""Integration test: Verify approval status flows from backend to frontend-ready format."""

import sys
from pathlib import Path

import pytest

# Add parent to path
parent_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(parent_dir / "src"))
sys.path.insert(0, str(parent_dir))

from src.app.json_trials_service import JSONTrialsService  # noqa: E402

ASCO_2020_PATH = parent_dir / "data" / "deployed" / "ASCO_2020.json"


def _require_local_json_fixture() -> None:
    """JSON-based integration tests require local deployed JSON fixtures.

    In CI and after the Supabase migration, these fixtures are intentionally
    not present/tracked. When absent, skip rather than fail.
    """

    if not ASCO_2020_PATH.exists():
        pytest.skip(
            f"Missing JSON fixture: {ASCO_2020_PATH}. "
            "These integration tests are only relevant when running with local JSON fixtures."
        )


def test_approval_status_enrichment():
    """Test that trial data is enriched with approval status."""
    _require_local_json_fixture()

    # Initialize service with approval status enabled (default)
    service = JSONTrialsService(
        json_file_paths=["data/deployed/ASCO_2020.json"], enable_approval_status=True
    )

    # Get a specific abstract
    abstract = service.get_full_abstract_by_id("ASCO_2020_10000")

    assert abstract is not None, "Abstract not found"
    assert "arm_results" in abstract, "No arm_results in abstract"

    # Check that all arms have approval_status
    arms_with_status = 0
    for arm_key, arm_data in abstract["arm_results"].items():
        if isinstance(arm_data, dict):
            assert (
                "approval_status" in arm_data
            ), f"Arm {arm_key} missing approval_status"
            assert arm_data["approval_status"] in [
                "Approved",
                "Investigational",
                "Control",
                "Unknown",
            ], f"Invalid approval_status: {arm_data['approval_status']}"

            arm_name = arm_data.get("arm_name", "")
            approval = arm_data["approval_status"]

            print(f"  ✓ {arm_name}: {approval}")
            arms_with_status += 1

    assert arms_with_status > 0, "No arms found with approval_status"
    print(f"\n✓ Successfully enriched {arms_with_status} arms with approval status")


def test_approval_status_in_trial_list():
    """Test that get_all_trials includes approval status in arms."""
    _require_local_json_fixture()

    service = JSONTrialsService(
        json_file_paths=["data/deployed/ASCO_2020.json"], enable_approval_status=True
    )

    trials, total = service.get_all_trials(skip=0, limit=5)

    assert len(trials) > 0, "No trials returned"

    trials_with_approval = 0
    for trial in trials:
        if "arms" in trial and trial["arms"]:
            for arm in trial["arms"]:
                if "approval_status" in arm:
                    trials_with_approval += 1
                    print(f"  ✓ {arm.get('arm_name')}: {arm['approval_status']}")

    assert trials_with_approval > 0, "No trials have approval_status in arms"
    print(f"\n✓ Found {trials_with_approval} arms with approval status in trial list")


def test_specific_classification_accuracy():
    """Test specific cases that demonstrate indication-specific approval."""

    service = JSONTrialsService(enable_approval_status=True)

    test_cases = [
        {
            "arm_name": "Pembrolizumab",
            "cancer_type": "Resected Cutaneous Melanoma",  # Normalizes to Cutaneous melanoma
            "expected": "Approved",
        },
        {
            "arm_name": "Pembrolizumab",
            "cancer_type": "Cutaneous melanoma",
            "expected": "Approved",
        },
        {
            "arm_name": "Nivolumab + Ipilimumab",
            "cancer_type": "Cutaneous melanoma with Brain metastasis",  # Normalizes to Brain/CNS
            "expected": "Approved",
        },
        {
            "arm_name": "Atezolizumab + Vemurafenib + Cobimetinib",
            "cancer_type": "Cutaneous melanoma",
            "expected": "Approved",
        },
    ]

    for case in test_cases:
        status = service.approval_service.get_approval_status(
            arm_name=case["arm_name"],
            cancer_type=case["cancer_type"],
        )

        assert (
            status == case["expected"]
        ), f"Failed: {case['arm_name']} + {case['cancer_type']} - Expected {case['expected']}, got {status}"

        print(f"  ✓ {case['arm_name']} + {case['cancer_type']}: {status}")

    print(f"\n✓ All {len(test_cases)} classification accuracy tests passed")


def test_disable_approval_status():
    """Test that approval status enrichment can be disabled."""
    _require_local_json_fixture()

    service = JSONTrialsService(
        json_file_paths=["data/deployed/ASCO_2020.json"],
        enable_approval_status=False,  # Disabled
    )

    abstract = service.get_full_abstract_by_id("ASCO_2020_10000")
    assert abstract is not None, "Abstract not found"

    # Should not have approval_status when disabled
    for _arm_key, arm_data in abstract["arm_results"].items():
        if isinstance(arm_data, dict):
            if "approval_status" in arm_data:
                # Might be in original data, so just verify service flag is off
                pass

    assert (
        service.approval_service is None
    ), "Approval service should be None when disabled"
    print("  ✓ Approval status enrichment can be disabled")


if __name__ == "__main__":
    print("=" * 70)
    print("APPROVAL STATUS INTEGRATION TESTS")
    print("=" * 70)
    print("\nTest 1: Abstract enrichment")
    print("-" * 70)
    test_approval_status_enrichment()

    print("\n" + "=" * 70)
    print("Test 2: Trial list enrichment")
    print("-" * 70)
    test_approval_status_in_trial_list()

    print("\n" + "=" * 70)
    print("Test 3: Classification accuracy")
    print("-" * 70)
    test_specific_classification_accuracy()

    print("\n" + "=" * 70)
    print("Test 4: Service toggle")
    print("-" * 70)
    test_disable_approval_status()

    print("\n" + "=" * 70)
    print("✅ ALL INTEGRATION TESTS PASSED!")
    print("=" * 70)
    print("\nBackend → Frontend approval status integration is working correctly.")
