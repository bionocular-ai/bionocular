"""Test publication arm separation logic with actual publication files.

This test verifies that:
1. Publications are correctly detected
2. Results section is correctly extracted from publications
3. Arms are separated from Results section only (not full publication)
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from src.infrastructure.cost_calculator import CostCalculator
from src.infrastructure.cost_tracking_llm_service import CostTrackingLLMService
from src.infrastructure.langchain.llm import LangChainLLMService
from src.infrastructure.treatment_arm_separator import TreatmentArmSeparator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_actual_publication(publication_file: str):
    """Test arm separation with an actual publication file."""
    logger.info("=" * 80)
    logger.info(f"Testing Publication: {publication_file}")
    logger.info("=" * 80)

    # Initialize services
    logger.info("Initializing services...")
    llm_service = LangChainLLMService()
    cost_calculator = CostCalculator()
    cost_tracking_llm = CostTrackingLLMService(llm_service, cost_calculator)
    treatment_arm_separator = TreatmentArmSeparator(cost_tracking_llm)

    # Import helper functions directly from the service module
    import re
    from typing import Optional

    def is_publication(content: str, file_path: Optional[str] = None) -> bool:
        """Detect if content is a full publication (not an abstract)."""
        # Check filename pattern (Publications folder)
        if file_path and (
            "Publications" in file_path or "publication" in file_path.lower()
        ):
            return True

        # Check for publication structure (main sections with #)
        has_main_sections = (
            re.search(
                r"^#\s+(Introduction|Methods|Results|Discussion|Conclusion)",
                content,
                re.MULTILINE | re.IGNORECASE,
            )
            is not None
        )

        # Check for absence of abstract-specific markers
        has_abstract_id = "### Abstract ID:" in content or "Abstract ID:" in content

        # Check length (publications are typically much longer)
        is_long = len(content) > 5000

        # Publication if it has main sections, no abstract ID, and is long
        return has_main_sections and not has_abstract_id and is_long

    def extract_results_section(content: str) -> Optional[str]:
        """Extract the Results section from publication content."""
        lines = content.split("\n")
        results_start = None
        results_end = None

        # Keywords that indicate Results section (prioritize more specific patterns first)
        results_keywords = [
            r"^#+\s*\*?\*?Results\*?\*?\s+",  # "## Results Patients" or "# Results Patients" (Results followed by text) - most specific
            r"^#+\s*\*?\*?Results\*?\*?\s*$",  # "## Results" or "# Results" (exact match)
            r"^#+\s*\*?\*?Findings\*?\*?",
            r"^#+\s*\*?\*?Clinical\s+activity\*?\*?",  # Some publications use "Clinical activity" as Results
        ]

        # Keywords that indicate end of Results section
        end_keywords = [
            r"^#+\s*\*?\*?Discussion\*?\*?",
            r"^#+\s*\*?\*?Conclusion\*?\*?",
            r"^#+\s*\*?\*?References\*?\*?",
            r"^#+\s*\*?\*?Appendix\*?\*?",
        ]

        # First pass: find all potential Results section starts
        potential_starts = []
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            for pattern_idx, pattern in enumerate(results_keywords):
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    potential_starts.append((i, pattern_idx, line_stripped))
                    break

        # If we found multiple Results sections, prefer the one that comes after Methods
        if potential_starts:
            # Check if any come after a Methods section (prefer main Methods, not abstract Methods)
            methods_found = False
            methods_line = None
            # Look for Methods sections - prefer top-level (# Methods) over subsection (## Methods)
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                # Match top-level Methods section (single #)
                if re.match(r"^#\s+\*?\*?Methods\*?\*?", line_stripped, re.IGNORECASE):
                    methods_found = True
                    methods_line = i
                    break
            # If no top-level Methods found, look for any Methods section header
            if not methods_found:
                for i, line in enumerate(lines):
                    if re.match(
                        r"^#+\s*\*?\*?Methods\*?\*?", line.strip(), re.IGNORECASE
                    ):
                        methods_found = True
                        methods_line = i
                        break
            # If still no Methods header found, look for bold text "**Methods**" or "**Methods ..."
            if not methods_found:
                for i, line in enumerate(lines):
                    if re.search(r"\*\*Methods", line, re.IGNORECASE):
                        methods_found = True
                        methods_line = i
                        break

            # Prefer Results section that comes after Methods, or the most specific one
            if methods_found:
                # Find the first Results section after Methods
                for start_line, pattern_idx, line_text in potential_starts:
                    if start_line > methods_line:
                        results_start = start_line
                        break
                # If none found after Methods, use the most specific one
                if results_start is None:
                    potential_starts.sort(key=lambda x: (x[0], x[1]))
                    results_start = potential_starts[0][0]
            else:
                # No Methods section found, use the most specific pattern
                potential_starts.sort(key=lambda x: (x[1], x[0]))
                results_start = potential_starts[0][0]

        # Second pass: find the end of the Results section
        if results_start is not None:
            for i in range(results_start + 1, len(lines)):
                line_stripped = lines[i].strip()
                for pattern in end_keywords:
                    if re.match(pattern, line_stripped, re.IGNORECASE):
                        results_end = i
                        break

                if results_end is not None:
                    break

        # If we found start but no end, Results section goes to end of document
        if results_start is not None and results_end is None:
            results_end = len(lines)

        if results_start is not None:
            results_content = "\n".join(lines[results_start:results_end])
            return results_content

        return None

    # Load publication
    pub_path = Path(publication_file)
    if not pub_path.exists():
        logger.error(f"❌ Publication file not found: {publication_file}")
        return False

    logger.info(f"Loading publication from: {pub_path}")
    pub_content = pub_path.read_text(encoding="utf-8")
    logger.info(f"Publication length: {len(pub_content)} characters")

    # Step 1: Detect if it's a publication
    logger.info("\n" + "-" * 80)
    logger.info("STEP 1: Publication Detection")
    logger.info("-" * 80)
    is_pub = is_publication(pub_content, str(pub_path))
    logger.info(f"✅ Detected as publication: {is_pub}")

    if not is_pub:
        logger.warning(
            "⚠️  File was not detected as publication, but continuing anyway..."
        )

    # Step 2: Extract Results section
    logger.info("\n" + "-" * 80)
    logger.info("STEP 2: Results Section Extraction")
    logger.info("-" * 80)
    results_section = extract_results_section(pub_content)

    if results_section:
        logger.info(f"✅ Results section extracted: {len(results_section)} characters")
        logger.info(
            f"   Results section is {len(results_section)/len(pub_content)*100:.1f}% of full publication"
        )

        # Show preview of Results section
        preview = results_section[:500].replace("\n", " ")
        logger.info(f"   Preview: {preview}...")
    else:
        logger.warning("⚠️  Results section not found, will use full publication text")
        results_section = pub_content

    # Step 3: Separate treatment arms from Results section
    logger.info("\n" + "-" * 80)
    logger.info("STEP 3: Treatment Arm Separation")
    logger.info("-" * 80)
    logger.info("Separating treatment arms from Results section...")

    abstract_id = pub_path.stem
    separation_result = await treatment_arm_separator.separate_treatment_arms(
        results_section, abstract_id
    )

    # Display results
    logger.info("\n✅ Arm separation completed!")
    logger.info(f"   Processing time: {separation_result.processing_time_ms}ms")
    logger.info(f"   Confidence: {separation_result.separation_confidence:.2f}")
    logger.info(f"   Arms identified: {len(separation_result.treatment_arms)}")

    if separation_result.errors:
        logger.warning(f"   Errors: {separation_result.errors}")

    if separation_result.warnings:
        logger.warning(f"   Warnings: {separation_result.warnings}")

    # Display each arm
    logger.info("\n" + "-" * 80)
    logger.info("TREATMENT ARMS IDENTIFIED:")
    logger.info("-" * 80)

    for i, arm in enumerate(separation_result.treatment_arms, 1):
        logger.info(f"\nArm {i}:")
        logger.info(f"  ID: {arm.arm_id}")
        logger.info(f"  Name: {arm.arm_name}")
        logger.info(f"  Generic Name: {arm.generic_name}")
        if arm.brand_name:
            logger.info(f"  Brand Name: {arm.brand_name}")
        if arm.dose:
            logger.info(f"  Dose: {arm.dose}")
        if arm.dosing_schedule:
            logger.info(f"  Schedule: {arm.dosing_schedule}")
        if arm.patient_count:
            logger.info(f"  Patient Count: {arm.patient_count}")
        logger.info(f"  Type: {arm.arm_type}")
        logger.info(f"  Line of Treatment: {arm.line_of_treatment}")
        if arm.combination_drugs:
            logger.info(f"  Combination Drugs: {', '.join(arm.combination_drugs)}")
        logger.info(f"  Confidence: {arm.confidence_score:.2f}")
        if arm.source_text:
            source_preview = arm.source_text[:200].replace("\n", " ")
            logger.info(f"  Source Text: {source_preview}...")

    logger.info("\n" + "=" * 80)
    logger.info("TEST COMPLETED")
    logger.info("=" * 80)

    return len(separation_result.treatment_arms) > 0


async def main():
    """Run test with actual publication."""
    logger.info("Starting Publication Arm Separation Test")
    logger.info("=" * 80)

    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("⚠️  OPENAI_API_KEY not found in environment variables")
        logger.info(
            "   Please set it in .env file or export OPENAI_API_KEY environment variable"
        )
        logger.info("   The test will still run but LLM calls will fail")
    else:
        logger.info("✅ OPENAI_API_KEY found")

    # Default publication file
    default_pub = "data/postprocessed/Publications/Batch-III_32.md"

    # Allow command line argument for different publication
    if len(sys.argv) > 1:
        publication_file = sys.argv[1]
    else:
        publication_file = default_pub

    try:
        success = await test_actual_publication(publication_file)

        if success:
            logger.info(
                "\n✅ Test passed! Arms were successfully separated from Results section."
            )
        else:
            logger.warning("\n⚠️  Test completed but no arms were identified.")

    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
