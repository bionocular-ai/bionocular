"""Test script to verify publication chunk type filtering for numeric attributes."""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.domain.extraction_models import AttributeType
from src.domain.rag_optimization_config import RAGOptimizationConfig
from src.infrastructure.langchain.chunking import ChunkTypeClassifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def test_chunk_type_classification():
    """Test that Clinical Activity and Findings are classified as Results."""
    logger.info("=" * 80)
    logger.info("TEST 1: Chunk Type Classification")
    logger.info("=" * 80)

    classifier = ChunkTypeClassifier()

    test_cases = [
        # (main_section, subsection, expected_type, description)
        ("results", "", "RESULTS", "Main Results section"),
        ("findings", "", "RESULTS", "Main Findings section"),
        ("clinical activity", "", "RESULTS", "Main Clinical Activity section"),
        ("results", "efficacy", "RESULTS", "Results > Efficacy subsection"),
        ("results", "safety", "RESULTS", "Results > Safety subsection"),
        (
            "results",
            "clinical activity",
            "RESULTS",
            "Results > Clinical Activity subsection",
        ),
        ("background", "", "BACKGROUND", "Background section (should NOT be Results)"),
        ("methods", "", "METHODS", "Methods section (should NOT be Results)"),
        (
            "conclusions",
            "",
            "CONCLUSIONS",
            "Conclusions section (should NOT be Results)",
        ),
    ]

    all_passed = True
    for main_section, subsection, expected_type, description in test_cases:
        headers = {
            "Main Section": main_section,
            "Subsection": subsection,
        }
        result = classifier.classify_chunk_type("", headers)
        result_type = (
            result.value.upper() if hasattr(result, "value") else str(result).upper()
        )
        expected_upper = expected_type.upper()

        if result_type == expected_upper:
            logger.info(f"✅ {description}: {result_type}")
        else:
            logger.error(
                f"❌ {description}: Expected {expected_upper}, got {result_type}"
            )
            all_passed = False

    return all_passed


def test_results_section_detection():
    """Test that _is_results_section correctly identifies Results sections."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Results Section Detection")
    logger.info("=" * 80)

    from src.domain.models import ChunkingConfiguration
    from src.infrastructure.langchain.chunking import LangChainChunkingService

    config = ChunkingConfiguration(
        chunk_size=800,
        chunk_overlap=150,
        strategy="hybrid",
    )
    chunking_service = LangChainChunkingService(configuration=config)

    test_cases = [
        # (main_section, subsection, expected, description)
        ("results", "", True, "Main Results section"),
        ("findings", "", True, "Main Findings section"),
        ("clinical activity", "", True, "Main Clinical Activity section"),
        ("results", "efficacy", True, "Results > Efficacy"),
        ("results", "safety", True, "Results > Safety"),
        ("results", "clinical activity", True, "Results > Clinical Activity"),
        ("background", "", False, "Background section"),
        ("methods", "", False, "Methods section"),
        ("conclusions", "", False, "Conclusions section"),
    ]

    all_passed = True
    for main_section, subsection, expected, description in test_cases:
        result = chunking_service._is_results_section(main_section, subsection)
        if result == expected:
            logger.info(f"✅ {description}: {result}")
        else:
            logger.error(f"❌ {description}: Expected {expected}, got {result}")
            all_passed = False

    return all_passed


def test_numeric_attribute_chunk_types():
    """Test that numeric attributes return correct chunk types for publications vs abstracts."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Numeric Attribute Chunk Type Filtering")
    logger.info("=" * 80)

    numeric_attributes = [
        AttributeType.AE,
        AttributeType.GRADE_3_PLUS_AE,
        AttributeType.MEDIAN_PFS,
        AttributeType.MEDIAN_OS,
        AttributeType.OBJECTIVE_RESPONSE_RATE,
    ]

    all_passed = True

    # Test publications
    logger.info("\n--- Testing Publications ---")
    for attr in numeric_attributes:
        chunk_types = RAGOptimizationConfig.get_required_chunk_types(
            attr, is_publication=True
        )
        expected = ["results", "table"]
        if chunk_types == expected:
            logger.info(f"✅ {attr.value} (publication): {chunk_types}")
        else:
            logger.error(
                f"❌ {attr.value} (publication): Expected {expected}, got {chunk_types}"
            )
            all_passed = False

    # Test abstracts
    logger.info("\n--- Testing Abstracts ---")
    for attr in numeric_attributes:
        chunk_types = RAGOptimizationConfig.get_required_chunk_types(
            attr, is_publication=False
        )
        expected = ["results", "table", "conclusions"]
        if chunk_types == expected:
            logger.info(f"✅ {attr.value} (abstract): {chunk_types}")
        else:
            logger.error(
                f"❌ {attr.value} (abstract): Expected {expected}, got {chunk_types}"
            )
            all_passed = False

    return all_passed


def test_non_numeric_attribute_chunk_types():
    """Test that non-numeric attributes still work correctly."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Non-Numeric Attribute Chunk Type Filtering")
    logger.info("=" * 80)

    non_numeric_attributes = [
        AttributeType.NCT_NUMBER,
        AttributeType.GENERIC_NAME,
        AttributeType.CANCER_TYPE,
    ]

    all_passed = True

    # Test NCT_NUMBER (special case)
    logger.info("\n--- Testing NCT_NUMBER (special case) ---")
    chunk_types_pub = RAGOptimizationConfig.get_required_chunk_types(
        AttributeType.NCT_NUMBER, is_publication=True
    )
    chunk_types_abs = RAGOptimizationConfig.get_required_chunk_types(
        AttributeType.NCT_NUMBER, is_publication=False
    )
    if chunk_types_pub is None:
        logger.info(f"✅ NCT_NUMBER (publication): {chunk_types_pub} (no filtering)")
    else:
        logger.error(
            f"❌ NCT_NUMBER (publication): Expected None, got {chunk_types_pub}"
        )
        all_passed = False

    if chunk_types_abs == ["clinical_trial"]:
        logger.info(f"✅ NCT_NUMBER (abstract): {chunk_types_abs}")
    else:
        logger.error(
            f"❌ NCT_NUMBER (abstract): Expected ['clinical_trial'], got {chunk_types_abs}"
        )
        all_passed = False

    # Test other non-numeric attributes
    logger.info("\n--- Testing Other Non-Numeric Attributes ---")
    for attr in [AttributeType.GENERIC_NAME, AttributeType.CANCER_TYPE]:
        chunk_types_pub = RAGOptimizationConfig.get_required_chunk_types(
            attr, is_publication=True
        )
        # Should return the default list (all chunk types except abstract_id)
        if chunk_types_pub and len(chunk_types_pub) > 10:
            logger.info(
                f"✅ {attr.value} (publication): Returns default list ({len(chunk_types_pub)} chunk types)"
            )
        else:
            logger.error(
                f"❌ {attr.value} (publication): Expected default list, got {chunk_types_pub}"
            )
            all_passed = False

    return all_passed


async def test_actual_publication_chunking():
    """Test chunking an actual publication file to see chunk types."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 5: Actual Publication Chunking")
    logger.info("=" * 80)

    from src.domain.models import ChunkingConfiguration
    from src.infrastructure.langchain.chunking import LangChainChunkingService

    publication_file = Path("data/postprocessed/Publications/Batch-II_11.md")
    if not publication_file.exists():
        logger.warning(f"⚠️  Publication file not found: {publication_file}")
        logger.info("Skipping actual publication chunking test")
        return True

    logger.info(f"Chunking publication: {publication_file}")

    config = ChunkingConfiguration(
        chunk_size=800,
        chunk_overlap=150,
        strategy="hybrid",
    )
    chunking_service = LangChainChunkingService(configuration=config)

    content = publication_file.read_text(encoding="utf-8")

    chunks = await chunking_service.chunk_content(
        content=content,
        configuration=config,
        document_id="test_publication",
        filename=str(publication_file),
    )

    # Analyze chunk types
    chunk_type_counts = {}
    results_chunks = []
    for chunk in chunks:
        chunk_type = chunk.chunk_type.value
        chunk_type_counts[chunk_type] = chunk_type_counts.get(chunk_type, 0) + 1

        # Check Results chunks for Clinical Activity or Findings
        if chunk_type == "results":
            metadata = chunk.metadata or {}
            main_section = metadata.get("Main Section", "").lower()
            subsection = metadata.get("Subsection", "").lower()
            results_chunks.append((main_section, subsection))

    logger.info(f"\nTotal chunks created: {len(chunks)}")
    logger.info("\nChunk type distribution:")
    for chunk_type, count in sorted(chunk_type_counts.items()):
        logger.info(f"  {chunk_type}: {count}")

    # Check for Results sections
    logger.info("\nResults section breakdown:")
    results_sections = set()
    for main, sub in results_chunks:
        section_name = f"{main} > {sub}" if sub else main
        results_sections.add(section_name)

    for section in sorted(results_sections):
        logger.info(f"  - {section}")

    # Verify Results chunks exist
    if chunk_type_counts.get("results", 0) > 0:
        logger.info(f"\n✅ Found {chunk_type_counts.get('results', 0)} Results chunks")
    else:
        logger.error("\n❌ No Results chunks found!")
        return False

    # Verify Tables exist
    if chunk_type_counts.get("table", 0) > 0:
        logger.info(f"✅ Found {chunk_type_counts.get('table', 0)} Table chunks")
    else:
        logger.warning("⚠️  No Table chunks found")

    return True


async def main():
    """Run all tests."""
    logger.info("=" * 80)
    logger.info("PUBLICATION CHUNK TYPE FILTERING TESTS")
    logger.info("=" * 80)

    results = []

    # Test 1: Chunk type classification
    results.append(("Chunk Type Classification", test_chunk_type_classification()))

    # Test 2: Results section detection
    results.append(("Results Section Detection", test_results_section_detection()))

    # Test 3: Numeric attribute chunk types
    results.append(
        ("Numeric Attribute Chunk Types", test_numeric_attribute_chunk_types())
    )

    # Test 4: Non-numeric attribute chunk types
    results.append(
        (
            "Non-Numeric Attribute Chunk Types",
            test_non_numeric_attribute_chunk_types(),
        )
    )

    # Test 5: Actual publication chunking
    results.append(
        ("Actual Publication Chunking", await test_actual_publication_chunking())
    )

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{status}: {test_name}")
        if not passed:
            all_passed = False

    logger.info("=" * 80)
    if all_passed:
        logger.info("🎉 ALL TESTS PASSED!")
    else:
        logger.error("❌ SOME TESTS FAILED")
    logger.info("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
