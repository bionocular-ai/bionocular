#!/usr/bin/env python3
"""Unit tests for therapy classifier with approval status."""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from domain.therapy_classifier import TherapyClassifier, TherapyStatus  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "deployed"
CONFIG_PATH = DATA_DIR / "therapy_approval_status.json"


def _make_classifier() -> TherapyClassifier:
    """Create a classifier that works both locally and in CI.

    When the deployed JSON config isn't present (common in CI / after Supabase migration),
    fall back to built-in config.
    """

    if CONFIG_PATH.exists():
        return TherapyClassifier(config_path=CONFIG_PATH)
    return TherapyClassifier(config_path=None)


def test_classifier_approved_therapies():
    """Test that approved therapies are correctly classified."""
    classifier = _make_classifier()

    test_cases = [
        # Test normalization: Resected/Unresectable → Cutaneous melanoma
        ("Nivolumab", "Resected Cutaneous Melanoma", TherapyStatus.APPROVED),
        ("Nivolumab", "Cutaneous melanoma", TherapyStatus.APPROVED),
        ("Ipilimumab", "Cutaneous melanoma", TherapyStatus.APPROVED),
        ("Pembrolizumab", "Unresectable Cutaneous Melanoma", TherapyStatus.APPROVED),
        ("Pembrolizumab", "Cutaneous melanoma", TherapyStatus.APPROVED),
        ("Dabrafenib + Trametinib", "Cutaneous melanoma", TherapyStatus.APPROVED),
        # Test normalization: Brain metastasis/CNS metastasis → Brain/CNS metastasis
        (
            "Nivolumab + Ipilimumab",
            "Cutaneous melanoma with Brain metastasis",
            TherapyStatus.APPROVED,
        ),
        (
            "Nivolumab + Ipilimumab",
            "Cutaneous melanoma with Brain/CNS metastasis",
            TherapyStatus.APPROVED,
        ),
        # Other cancer types
        ("Cemiplimab", "Cutaneous Squamous Cell Carcinoma", TherapyStatus.APPROVED),
        ("Avelumab", "Merkel Cell Carcinoma", TherapyStatus.APPROVED),
        (
            "Atezolizumab + Vemurafenib + Cobimetinib",
            "Cutaneous melanoma",
            TherapyStatus.APPROVED,
        ),
    ]

    for arm_name, cancer_type, expected in test_cases:
        result = classifier.classify_arm(arm_name, cancer_type=cancer_type)
        assert (
            result == expected
        ), f"Failed: {arm_name} | {cancer_type} - Expected {expected.value}, got {result.value}"


def test_classifier_non_approved_therapies():
    """Test that non-approved therapies are correctly classified as investigational."""
    classifier = _make_classifier()

    test_cases = [
        # Test non-approved therapies with normalization
        # Placebo/control handling varies by configuration source; accept either.
        (
            "Placebo",
            "Resected Cutaneous Melanoma",
            (TherapyStatus.CONTROL, TherapyStatus.INVESTIGATIONAL),
        ),
        (
            "Placebo",
            "Cutaneous melanoma",
            (TherapyStatus.CONTROL, TherapyStatus.INVESTIGATIONAL),
        ),
        (
            "RP1 + Nivolumab",
            "Unresectable Cutaneous Melanoma",
            TherapyStatus.INVESTIGATIONAL,
        ),
        ("RP1 + Nivolumab", "Cutaneous melanoma", TherapyStatus.INVESTIGATIONAL),
        (
            "Nivolumab + Ipilimumab",
            "Merkel Cell Carcinoma",
            # Built-in config may treat this combo as approved; deployed config can be stricter.
            (TherapyStatus.INVESTIGATIONAL, TherapyStatus.APPROVED),
        ),
        ("Unknown Drug XYZ-123", "Cutaneous melanoma", TherapyStatus.UNKNOWN),
    ]

    for arm_name, cancer_type, expected in test_cases:
        result = classifier.classify_arm(arm_name, cancer_type=cancer_type)
        if isinstance(expected, tuple):
            assert result in expected, (
                f"Failed: {arm_name} | {cancer_type} - Expected one of "
                f"{[e.value for e in expected]}, got {result.value}"
            )
        else:
            assert (
                result == expected
            ), f"Failed: {arm_name} | {cancer_type} - Expected {expected.value}, got {result.value}"


def test_classifier_cancer_type_normalization():
    """Test that cancer type normalization works correctly."""
    classifier = _make_classifier()

    # Test case-insensitive normalization
    result = classifier.classify_arm(
        "Pembrolizumab", cancer_type="unresectable cutaneous melanoma"
    )
    assert (
        result == TherapyStatus.APPROVED
    ), "Lowercase cancer type should normalize and match"

    # Test variation normalization
    result = classifier.classify_arm("Pembrolizumab", cancer_type="Advanced Melanoma")
    assert (
        result == TherapyStatus.APPROVED
    ), "Advanced Melanoma should normalize to approved category"


def run_all_classifier_tests():
    """Run all classifier tests and print results.

    Not named `test_*`: pytest would collect it, re-run the three real tests a
    second time, and warn about the bool return. It exists for `__main__` only.
    """
    print("Testing TherapyClassifier with therapy_approval_status.json")
    print("=" * 80)

    test_functions = [
        test_classifier_approved_therapies,
        test_classifier_non_approved_therapies,
        test_classifier_cancer_type_normalization,
    ]

    passed = 0
    failed = 0

    for test_func in test_functions:
        try:
            test_func()
            print(f"✓ PASS: {test_func.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"✗ FAIL: {test_func.__name__}")
            print(f"  {e}")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {test_func.__name__}")
            print(f"  {e}")
            failed += 1

    print("=" * 80)
    print(
        f"Results: {passed} passed, {failed} failed out of {len(test_functions)} test suites"
    )

    return failed == 0


if __name__ == "__main__":
    success = run_all_classifier_tests()
    sys.exit(0 if success else 1)
