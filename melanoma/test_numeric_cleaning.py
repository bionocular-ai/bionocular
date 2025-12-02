#!/usr/bin/env python3
"""Test script for numeric value cleaning functionality."""

import sys
from pathlib import Path

# Add the melanoma directory to path so we can import from src
melanoma_dir = Path(__file__).parent
sys.path.insert(0, str(melanoma_dir))

from src.domain.extraction_models import AttributeType
from src.infrastructure.attribute_extractor import clean_numeric_value


def test_clean_numeric_value():
    """Test the clean_numeric_value function with various inputs."""

    test_cases = [
        # (input_value, attribute_type, expected_output, description)
        ("24%", AttributeType.OBJECTIVE_RESPONSE_RATE, 24.0, "Percentage with % sign"),
        ("57%", AttributeType.OBJECTIVE_RESPONSE_RATE, 57.0, "Another percentage"),
        ("12 months", AttributeType.MEDIAN_PFS, 12.0, "Time unit: months"),
        ("24 months", AttributeType.MEDIAN_OS, 24.0, "Time unit: months"),
        ("45.5%", AttributeType.GRADE_3_PLUS_AE, 45.5, "Decimal percentage"),
        ("30%", AttributeType.OBJECTIVE_RESPONSE_RATE, 30.0, "Percentage"),
        ("13%", AttributeType.OBJECTIVE_RESPONSE_RATE, 13.0, "Percentage"),
        ("38%", AttributeType.OBJECTIVE_RESPONSE_RATE, 38.0, "Percentage"),
        ("34%", AttributeType.OBJECTIVE_RESPONSE_RATE, 34.0, "Percentage"),
        ("24", AttributeType.OBJECTIVE_RESPONSE_RATE, 24.0, "Plain number string"),
        (24, AttributeType.OBJECTIVE_RESPONSE_RATE, 24.0, "Integer input"),
        (24.5, AttributeType.OBJECTIVE_RESPONSE_RATE, 24.5, "Float input"),
        ("Not found", AttributeType.OBJECTIVE_RESPONSE_RATE, None, "Not found string"),
        ("", AttributeType.OBJECTIVE_RESPONSE_RATE, None, "Empty string"),
        (None, AttributeType.OBJECTIVE_RESPONSE_RATE, None, "None input"),
        ("NR", AttributeType.MEDIAN_PFS, "NR", "Not reached for survival metric"),
        ("not reached", AttributeType.MEDIAN_OS, "NR", "Not reached variation"),
        ("12.5 months", AttributeType.MEDIAN_PFS, 12.5, "Decimal with months"),
        ("6 years", AttributeType.MEDIAN_OS, 72.0, "Years to months for OS"),
        ("18 mo", AttributeType.MEDIAN_PFS, 18.0, "Abbreviated months"),
        (
            "100 patients",
            AttributeType.NUMBER_OF_PATIENTS,
            100,
            "Integer attribute with text",
        ),
        ("50.0%", AttributeType.OBJECTIVE_RESPONSE_RATE, 50.0, "Decimal percentage"),
        (
            "46.1 weeks",
            AttributeType.MEDIAN_OS,
            11.525,
            "Weeks to months conversion for median OS",
        ),
        ("24 weeks", AttributeType.MEDIAN_PFS, 6.0, "Weeks to months for PFS"),
        (
            "365 days",
            AttributeType.MEDIAN_DOR,
            12.166666666666666,
            "Days to months for DOR",
        ),
        ("2 years", AttributeType.MEDIAN_OS, 24.0, "Years to months for OS"),
        ("12 months", AttributeType.MEDIAN_OS, 12.0, "Months (no conversion needed)"),
        ("8 weeks", AttributeType.TTR, 2.0, "Weeks to months for TTR"),
    ]

    print("Testing clean_numeric_value function:\n")
    print(f"{'Input':<25} {'Attribute':<30} {'Expected':<15} {'Got':<15} {'Status'}")
    print("-" * 100)

    passed = 0
    failed = 0

    for input_value, attr_type, expected, description in test_cases:
        result = clean_numeric_value(input_value, attr_type)
        status = "✓ PASS" if result == expected else "✗ FAIL"

        if result == expected:
            passed += 1
        else:
            failed += 1

        input_str = repr(input_value) if input_value is not None else "None"
        attr_str = (
            attr_type.value[:28] if len(attr_type.value) > 28 else attr_type.value
        )
        expected_str = repr(expected) if expected is not None else "None"
        result_str = repr(result) if result is not None else "None"

        print(
            f"{input_str:<25} {attr_str:<30} {expected_str:<15} {result_str:<15} {status}"
        )
        if result != expected:
            print(f"  └─ Description: {description}")

    print("\n" + "=" * 100)
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")

    if failed == 0:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = test_clean_numeric_value()
    sys.exit(exit_code)
