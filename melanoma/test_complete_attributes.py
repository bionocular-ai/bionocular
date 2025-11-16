"""Complete test for all clinical trial attributes."""

import logging
from typing import Optional

from src.app.clinical_trials_service import ClinicalTrialsService
from src.domain.extraction_models import AttributeType
from src.infrastructure.clinical_trials.factory import create_clinical_trials_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def format_value(value: Optional[str | bool | int]) -> str:
    """Format value for display."""
    if value is None:
        return "❌ Not found"
    if isinstance(value, bool):
        return "✅ YES" if value else "❌ NO"
    if value == "":
        return "❌ Empty"
    return f"✅ {value}"


def test_all_attributes(nct_number: str = "NCT01844505"):
    """Test all attributes from the user's complete list.
    
    Args:
        nct_number: NCT number to test (default: NCT01844505)
    """
    logger.info("=" * 100)
    logger.info(f"COMPLETE ATTRIBUTE TEST - {nct_number}")
    logger.info("=" * 100)

    service = create_clinical_trials_service()

    logger.info(f"\nFetching data for {nct_number}...\n")
    trial_data = service.get_trial_data(nct_number)

    if not trial_data:
        logger.error("Failed to fetch trial data")
        return False

    # Complete list of attributes to test
    attributes_to_test = {
        # Basic Information
        "NCT Number": AttributeType.NCT_NUMBER,
        "Trial Name": AttributeType.TRIAL_NAME,
        "Clinical Trial Phase": AttributeType.CLINICAL_TRIAL_PHASE,
        "Study Type": AttributeType.STUDY_TYPE,
        
        # Endpoints
        "Primary endpoint": AttributeType.PRIMARY_ENDPOINT,
        "Secondary endpoint": AttributeType.SECONDARY_ENDPOINT,
        
        # Dates
        "Study start date": AttributeType.STUDY_START_DATE,
        "Primary Completion (Estimated)": AttributeType.PRIMARY_COMPLETION_DATE,
        "Study completion date": AttributeType.STUDY_COMPLETION_DATE,
        "First results": AttributeType.FIRST_RESULTS,
        
        # Enrollment
        "Enrollment (Estimated)": AttributeType.NUMBER_OF_PATIENTS,
        
        # Location
        "Trial run in Europe": AttributeType.TRIAL_RUN_IN_EUROPE,
        "Trial run in US": AttributeType.TRIAL_RUN_IN_US,
        "Trial run in China": AttributeType.TRIAL_RUN_IN_CHINA,
        
        # Eligibility Attributes
        "Chemotherapy Naive": AttributeType.CHEMOTHERAPY_NAIVE,
        "Chemotherapy Failed": AttributeType.CHEMOTHERAPY_FAILED,
        "ICI Naive": AttributeType.ICI_NAIVE,
        "ICI Failed": AttributeType.ICI_FAILED,
        "Ipilimumab-failure": AttributeType.IPILIMUMAB_FAILURE,
        "Anti PD-1/L1-failure": AttributeType.ANTI_PD1_FAILURE,
        "BRAF-mutation": AttributeType.BRAF_MUTATION,
        "NRAS-Mutation": AttributeType.NRAS_MUTATION,
        "Line of Treatment": AttributeType.LINE_OF_TREATMENT,
        "Biomarker Inclusion": AttributeType.BIOMARKER_INCLUSION,
        "Biomarkers Inclusion Criteria": AttributeType.BIOMARKERS_INCLUSION_CRITERIA,
        "Biomarkers Exclusion Criteria": AttributeType.BIOMARKERS_EXCLUSION_CRITERIA,
        
        # Arm-specific attributes (from first arm)
        "Dosage": AttributeType.DOSAGE,
        "Type of dosing": AttributeType.TYPE_OF_DOSING,
        "Mechanism of action": AttributeType.MECHANISM_OF_ACTION,
        "Target Protein": AttributeType.TARGET_PROTEIN,
        "Type of therapy": AttributeType.TYPE_OF_THERAPY,
    }

    logger.info("STUDY-WIDE ATTRIBUTES")
    logger.info("-" * 100)

    results = {}
    for attr_name, attr_type in attributes_to_test.items():
        # Try get_attribute_value first, but also check raw data if it returns None
        value = service.get_attribute_value(nct_number, attr_type)
        if value is None:
            # Check raw trial data directly for attributes that might not be in api_sourced list
            value = service._get_attribute_from_data(trial_data, attr_type)
        results[attr_name] = value
        logger.info(f"{attr_name:.<50} {format_value(value)}")

    # Arm-specific attributes
    logger.info("\n" + "=" * 100)
    logger.info("ARM-SPECIFIC ATTRIBUTES (Per Arm)")
    logger.info("=" * 100)

    for i, arm in enumerate(trial_data.treatment_arms):
        logger.info(f"\n{'=' * 100}")
        logger.info(f"ARM {i + 1}: {arm.arm_label}")
        logger.info(f"{'=' * 100}")
        logger.info(f"  Generic Name: {format_value(arm.generic_name)}")
        logger.info(f"  Brand Name: {format_value(arm.brand_name)}")
        logger.info(f"  Dosage: {format_value(arm.dosage)}")
        logger.info(f"  Type of Dosing: {format_value(arm.type_of_dosing)}")
        logger.info(f"  Mechanism of Action: {format_value(arm.mechanism_of_action)}")
        logger.info(f"  Target Protein: {format_value(arm.target_protein)}")
        logger.info(f"  Type of Therapy: {format_value(arm.type_of_therapy)}")
        logger.info(f"  Line of Treatment: {format_value(arm.line_of_treatment)}")

    # Summary
    logger.info("\n" + "=" * 100)
    logger.info("SUMMARY")
    logger.info("=" * 100)

    total_attributes = len(attributes_to_test)
    found_attributes = sum(1 for v in results.values() if v is not None and v != "")
    logger.info(f"Total Attributes Tested: {total_attributes}")
    logger.info(f"Attributes Found: {found_attributes}")
    logger.info(f"Attributes Missing: {total_attributes - found_attributes}")
    logger.info(f"Success Rate: {(found_attributes / total_attributes * 100):.1f}%")

    return True


if __name__ == "__main__":
    import sys
    
    # Allow NCT number to be passed as command line argument
    if len(sys.argv) > 1:
        nct_number = sys.argv[1]
    else:
        nct_number = "NCT01844505"  # Default
    
    test_all_attributes(nct_number)

