#!/usr/bin/env python3
"""Test script to verify TreatmentArm model has arm_metadata field."""

from src.domain.treatment_arm_models import TreatmentArm


def test_treatment_arm_model():
    """Test that TreatmentArm model has arm_metadata field."""
    print("Testing TreatmentArm model...")

    # Create a test TreatmentArm
    arm = TreatmentArm(
        arm_id="test_arm_1",
        arm_name="Test Arm",
        generic_name="Test Drug",
        arm_metadata={
            "nct_number": "NCT123456789",
            "generic_name": "Test Drug",
            "test_data": "test_value",
        },
    )

    print("✅ TreatmentArm created successfully")
    print(f"   arm_id: {arm.arm_id}")
    print(f"   arm_name: {arm.arm_name}")
    print(f"   generic_name: {arm.generic_name}")
    print(f"   arm_metadata: {arm.arm_metadata}")

    # Test accessing arm_metadata
    if hasattr(arm, "arm_metadata"):
        print("✅ arm_metadata field exists")
        print(f"   NCT number: {arm.arm_metadata.get('nct_number')}")
        print(f"   Generic name: {arm.arm_metadata.get('generic_name')}")
    else:
        print("❌ arm_metadata field missing!")
        return False

    # Test JSON serialization
    try:
        arm_dict = arm.dict()
        print("✅ JSON serialization works")
        print(f"   arm_metadata in dict: {'arm_metadata' in arm_dict}")
    except Exception as e:
        print(f"❌ JSON serialization failed: {e}")
        return False

    print("✅ All tests passed!")
    return True


if __name__ == "__main__":
    test_treatment_arm_model()
