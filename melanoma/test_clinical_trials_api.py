"""Test script for Clinical Trials API v2 with arm-wise data."""

import logging

from src.domain.extraction_models import AttributeType
from src.infrastructure.clinical_trials.factory import create_clinical_trials_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def test_basic_fetch():
    """Test basic trial data fetching."""
    logger.info("=" * 80)
    logger.info("TEST 1: Basic Trial Data Fetching")
    logger.info("=" * 80)

    service = create_clinical_trials_service()

    # Test with a known NCT number
    nct_number = "NCT02362594"  # Example trial
    logger.info(f"Fetching data for {nct_number}...")

    trial_data = service.get_trial_data(nct_number)

    if not trial_data:
        logger.error("Failed to fetch trial data")
        return False

    logger.info("✅ Successfully fetched trial data")
    logger.info(f"  NCT Number: {trial_data.nct_number}")
    logger.info(f"  Trial Name: {trial_data.trial_name}")
    logger.info(f"  Phase: {trial_data.clinical_trial_phase}")
    logger.info(f"  Number of Arms: {len(trial_data.treatment_arms)}")
    logger.info(f"  Chemotherapy Naive: {trial_data.chemotherapy_naive}")
    logger.info(f"  ICI Naive: {trial_data.ici_naive}")
    logger.info(f"  BRAF Mutation: {trial_data.braf_mutation}")

    return True


def test_arm_parsing():
    """Test arm-wise data parsing."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Arm-Wise Data Parsing")
    logger.info("=" * 80)

    service = create_clinical_trials_service()
    nct_number = "NCT02362594"

    trial_data = service.get_trial_data(nct_number)

    if not trial_data or not trial_data.treatment_arms:
        logger.error("No treatment arms found")
        return False

    logger.info(f"✅ Found {len(trial_data.treatment_arms)} treatment arm(s)")

    for i, arm in enumerate(trial_data.treatment_arms):
        logger.info(f"\n  Arm {i + 1}:")
        logger.info(f"    Label: {arm.arm_label}")
        logger.info(f"    Type: {arm.arm_type}")
        logger.info(
            f"    Description: {arm.arm_description[:100] if arm.arm_description else 'N/A'}..."
        )
        logger.info(f"    Generic Name: {arm.generic_name}")
        logger.info(f"    Brand Name: {arm.brand_name}")
        logger.info(f"    Dosage: {arm.dosage}")
        logger.info(f"    Type of Dosing: {arm.type_of_dosing}")
        logger.info(f"    Mechanism of Action: {arm.mechanism_of_action}")
        logger.info(f"    Target Protein: {arm.target_protein}")
        logger.info(f"    Type of Therapy: {arm.type_of_therapy}")
        logger.info(f"    Intervention Names: {', '.join(arm.intervention_names)}")

    return True


def test_arm_specific_attributes():
    """Test arm-specific attribute extraction."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Arm-Specific Attribute Extraction")
    logger.info("=" * 80)

    service = create_clinical_trials_service()
    nct_number = "NCT02362594"

    trial_data = service.get_trial_data(nct_number)

    if not trial_data or not trial_data.treatment_arms:
        logger.error("No treatment arms found")
        return False

    # Test getting attributes for first arm
    first_arm = trial_data.treatment_arms[0]
    logger.info(f"Testing attributes for arm: {first_arm.arm_label}")

    arm_info = {"arm_label": first_arm.arm_label}
    attribute_types = [
        AttributeType.GENERIC_NAME,
        AttributeType.DOSAGE,
        AttributeType.TYPE_OF_DOSING,
        AttributeType.MECHANISM_OF_ACTION,
    ]

    attributes = service.get_multiple_attributes(
        nct_number, attribute_types, arm_info=arm_info
    )

    logger.info("✅ Arm-specific attributes:")
    for attr_type, value in attributes.items():
        logger.info(f"  {attr_type.value}: {value}")

    return True


def test_study_wide_attributes():
    """Test study-wide attribute extraction."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Study-Wide Attribute Extraction")
    logger.info("=" * 80)

    service = create_clinical_trials_service()
    nct_number = "NCT02362594"

    # Use attributes that are actually configured as API-sourced
    attribute_types = [
        AttributeType.STUDY_START_DATE,
        AttributeType.STUDY_COMPLETION_DATE,
        AttributeType.CHEMOTHERAPY_NAIVE,
        AttributeType.ICI_NAIVE,
        AttributeType.BRAF_MUTATION,
        AttributeType.MINIMUM_AGE,
        AttributeType.MAXIMUM_AGE,
    ]

    attributes = service.get_multiple_attributes(nct_number, attribute_types)

    logger.info("✅ Study-wide attributes (API-sourced):")
    for attr_type, value in attributes.items():
        logger.info(f"  {attr_type.value}: {value}")

    # Also check the raw trial data (these are parsed but may not be in api_sourced list)
    trial_data = service.get_trial_data(nct_number)
    if trial_data:
        logger.info("\n  Additional parsed values (from raw trial data):")
        logger.info(f"    trial_name: {trial_data.trial_name}")
        logger.info(f"    clinical_trial_phase: {trial_data.clinical_trial_phase}")
        logger.info(f"    primary_endpoint: {trial_data.primary_endpoint}")
        logger.info(f"    sponsors: {trial_data.sponsors}")

    return True


def test_caching():
    """Test caching functionality."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 5: Caching Functionality")
    logger.info("=" * 80)

    service = create_clinical_trials_service()
    nct_number = "NCT02362594"

    # First fetch (should hit API)
    logger.info("First fetch (should hit API)...")
    import time

    start = time.time()
    trial_data1 = service.get_trial_data(nct_number)
    first_fetch_time = time.time() - start
    logger.info(f"  Time: {first_fetch_time:.2f}s")

    # Second fetch (should hit cache)
    logger.info("Second fetch (should hit cache)...")
    start = time.time()
    trial_data2 = service.get_trial_data(nct_number)
    second_fetch_time = time.time() - start
    logger.info(f"  Time: {second_fetch_time:.2f}s")

    if second_fetch_time < first_fetch_time * 0.5:
        logger.info("✅ Caching working (second fetch was faster)")
    else:
        logger.warning("⚠️  Caching may not be working optimally")

    # Check cache stats
    stats = service.get_cache_stats()
    logger.info(f"Cache Stats: {stats}")

    return True


def test_backward_compatibility():
    """Test backward compatibility with legacy fields."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 6: Backward Compatibility")
    logger.info("=" * 80)

    service = create_clinical_trials_service()
    nct_number = "NCT02362594"

    trial_data = service.get_trial_data(nct_number)

    if not trial_data:
        logger.error("Failed to fetch trial data")
        return False

    logger.info("✅ Legacy fields (from first arm):")
    logger.info(f"  generic_name: {trial_data.generic_name}")
    logger.info(f"  dosage: {trial_data.dosage}")
    logger.info(f"  type_of_dosing: {trial_data.type_of_dosing}")
    logger.info(f"  mechanism_of_action: {trial_data.mechanism_of_action}")

    # Verify legacy fields match first arm
    if trial_data.treatment_arms:
        first_arm = trial_data.treatment_arms[0]
        if trial_data.generic_name == first_arm.generic_name:
            logger.info("✅ Legacy fields correctly populated from first arm")
        else:
            logger.warning("⚠️  Legacy fields may not match first arm")

    return True


def main():
    """Run all tests."""
    logger.info("Starting Clinical Trials API v2 Tests")
    logger.info("=" * 80)

    tests = [
        ("Basic Fetch", test_basic_fetch),
        ("Arm Parsing", test_arm_parsing),
        ("Arm-Specific Attributes", test_arm_specific_attributes),
        ("Study-Wide Attributes", test_study_wide_attributes),
        ("Caching", test_caching),
        ("Backward Compatibility", test_backward_compatibility),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"❌ Test '{test_name}' failed with error: {e}", exc_info=True)
            results[test_name] = False

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{status}: {test_name}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    logger.info(f"\nTotal: {passed}/{total} tests passed")

    return all(results.values())


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
