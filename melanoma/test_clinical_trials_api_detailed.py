"""Detailed test to inspect API response structure."""

import json
import logging

from src.infrastructure.clinical_trials.api_client import ClinicalTrialsGovAPIClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def inspect_api_response():
    """Inspect the raw API response structure."""
    client = ClinicalTrialsGovAPIClient()
    nct_number = "NCT02362594"

    logger.info(f"Fetching raw API response for {nct_number}...")
    api_json = client.fetch_trial_data(nct_number)

    if not api_json:
        logger.error("Failed to fetch API response")
        return

    # Inspect armsInterventionsModule
    protocol = api_json.get("protocolSection", {})
    interventions_module = protocol.get("armsInterventionsModule", {})

    logger.info("\n=== Arms Structure ===")
    arm_groups = interventions_module.get("armGroups", [])
    logger.info(f"Number of arm groups: {len(arm_groups)}")

    for i, arm in enumerate(arm_groups):
        logger.info(f"\nArm {i + 1}:")
        logger.info(f"  Label: {arm.get('label')}")
        logger.info(f"  Type: {arm.get('type')}")
        logger.info(f"  Description: {arm.get('description', '')[:200]}...")
        logger.info(f"  Intervention Names: {arm.get('interventionNames', [])}")

    logger.info("\n=== Interventions Structure ===")
    interventions = interventions_module.get("interventions", [])
    logger.info(f"Number of interventions: {len(interventions)}")

    for i, intervention in enumerate(interventions):
        logger.info(f"\nIntervention {i + 1}:")
        logger.info(f"  Name: {intervention.get('name')}")
        logger.info(f"  Type: {intervention.get('type')}")
        logger.info(f"  Description: {intervention.get('description', '')[:200]}...")

    # Save full response for inspection
    output_file = "api_response_sample.json"
    with open(output_file, "w") as f:
        json.dump(api_json, f, indent=2)
    logger.info(f"\n✅ Full API response saved to {output_file}")


if __name__ == "__main__":
    inspect_api_response()

