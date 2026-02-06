#!/usr/bin/env python3
"""Unit tests for approval status service integration."""

import sys
from pathlib import Path

# Add parent directories to path
parent_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(parent_dir / "src"))
sys.path.insert(0, str(parent_dir))

from src.app.approval_status_service import ApprovalStatusService  # noqa: E402


def test_approval_status_service():
    """Test that approval status service classifies therapies correctly."""
    service = ApprovalStatusService()

    # Test approved therapy
    status = service.get_approval_status(
        arm_name="Pembrolizumab", cancer_type="Unresectable Cutaneous Melanoma"
    )
    assert status == "Approved", f"Expected Approved, got {status}"

    # Test control therapy
    status = service.get_approval_status(
        arm_name="Placebo", cancer_type="Resected Cutaneous Melanoma"
    )
    assert status in [
        "Control",
        "Investigational",
    ], f"Expected Control or Investigational, got {status}"

    # Test indication-specific approval with Brain/CNS metastasis
    # Note: After normalization, Resected/Unresectable → Cutaneous melanoma
    # So we use Brain/CNS metastasis for a clearly approved indication
    status_approved = service.get_approval_status(
        arm_name="Nivolumab + Ipilimumab",
        cancer_type="Cutaneous melanoma with Brain metastasis",  # Normalizes to Brain/CNS metastasis
    )
    assert (
        status_approved == "Approved"
    ), f"Expected Approved for Brain/CNS metastasis, got {status_approved}"

    # Test non-approved therapy
    status_non_approved = service.get_approval_status(
        arm_name="RP1 + Nivolumab",
        cancer_type="Unresectable Cutaneous Melanoma",  # Normalizes to Cutaneous melanoma
    )
    assert (
        status_non_approved == "Investigational"
    ), f"Expected Investigational, got {status_non_approved}"

    print("✓ All approval status service tests passed")


def test_enrich_arm_with_approval_status():
    """Test enriching an arm dictionary with approval status."""
    service = ApprovalStatusService()

    arm = {
        "arm_name": "Pembrolizumab",
        "attributes": {
            "AttributeType.CANCER_TYPE": {"value": "Unresectable Cutaneous Melanoma"}
        },
    }

    enriched_arm = service.enrich_arm_with_approval_status(arm)

    assert "approval_status" in enriched_arm, "approval_status field not added"
    assert (
        enriched_arm["approval_status"] == "Approved"
    ), f"Expected Approved, got {enriched_arm['approval_status']}"
    assert enriched_arm["arm_name"] == "Pembrolizumab", "Original arm data modified"

    print("✓ Arm enrichment test passed")


def test_cancer_type_normalization():
    """Test that cancer types are normalized correctly."""
    service = ApprovalStatusService()

    # Test case-insensitive normalization
    status = service.get_approval_status(
        arm_name="Pembrolizumab",
        cancer_type="unresectable cutaneous melanoma",  # lowercase
    )
    assert status == "Approved", f"Expected Approved with lowercase input, got {status}"

    # Test variation normalization
    status = service.get_approval_status(
        arm_name="Pembrolizumab",
        cancer_type="Advanced Melanoma",  # should normalize to Cutaneous melanoma
    )
    assert status == "Approved", f"Expected Approved with variation, got {status}"

    print("✓ Cancer type normalization test passed")


if __name__ == "__main__":
    test_approval_status_service()
    test_enrich_arm_with_approval_status()
    test_cancer_type_normalization()
    print("\n" + "=" * 60)
    print("All approval status service tests passed!")
    print("=" * 60)
