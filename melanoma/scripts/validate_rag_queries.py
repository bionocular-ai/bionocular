"""Validation script for RAG query templates.

This script validates that all attributes in prompt_templates.py have
corresponding RAG query templates in rag_query_templates.yaml.
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.domain.extraction_models import AttributeType
from src.infrastructure.rag_config_loader import RAGConfigLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_query_templates():
    """Validate that all attributes have RAG query templates."""

    logger.info("=" * 80)
    logger.info("RAG Query Templates Validation")
    logger.info("=" * 80)

    # Load RAG configuration
    config_loader = RAGConfigLoader()

    # Get all attribute types
    all_attributes = list(AttributeType)

    logger.info(f"\nTotal attributes defined: {len(all_attributes)}")
    logger.info(f"Attributes with RAG templates: {config_loader.get_template_count()}")

    # Check coverage
    missing_templates = []
    covered_templates = []

    for attr_type in all_attributes:
        templates = config_loader.get_query_templates(attr_type)
        if templates:
            covered_templates.append(attr_type)
        else:
            missing_templates.append(attr_type)

    # Report results
    coverage_percent = (len(covered_templates) / len(all_attributes)) * 100

    logger.info(f"\n{'='*80}")
    logger.info(
        f"Coverage: {coverage_percent:.1f}% ({len(covered_templates)}/{len(all_attributes)})"
    )
    logger.info(f"{'='*80}")

    if covered_templates:
        logger.info(f"\n✅ Attributes with RAG templates ({len(covered_templates)}):")
        for attr_type in sorted(covered_templates, key=lambda x: x.value):
            templates = config_loader.get_query_templates(attr_type)
            logger.info(f"  ✓ {attr_type.value:40s} ({len(templates)} queries)")

    if missing_templates:
        logger.warning(
            f"\n⚠️  Attributes missing RAG templates ({len(missing_templates)}):"
        )
        for attr_type in sorted(missing_templates, key=lambda x: x.value):
            logger.warning(f"  ✗ {attr_type.value}")

    # Show sample templates
    logger.info(f"\n{'='*80}")
    logger.info("Sample Query Templates")
    logger.info(f"{'='*80}")

    sample_attributes = [
        AttributeType.NCT_NUMBER,
        AttributeType.GENERIC_NAME,
        AttributeType.P_VALUE_OS,
        AttributeType.OBJECTIVE_RESPONSE_RATE,
        AttributeType.GRADE_3_PLUS_AE,
    ]

    for attr_type in sample_attributes:
        templates = config_loader.get_query_templates(attr_type)
        if templates:
            logger.info(f"\n{attr_type.value}:")
            for i, template in enumerate(templates[:3], 1):
                logger.info(f"  {i}. {template}")
            if len(templates) > 3:
                logger.info(f"  ... and {len(templates) - 3} more")

    # Quality checks
    logger.info(f"\n{'='*80}")
    logger.info("Quality Checks")
    logger.info(f"{'='*80}")

    # Check for duplicate queries
    all_queries = set()
    duplicate_queries = []

    for attr_type in covered_templates:
        templates = config_loader.get_query_templates(attr_type)
        for template in templates:
            if template in all_queries:
                duplicate_queries.append((attr_type, template))
            all_queries.add(template)

    if duplicate_queries:
        logger.warning(f"\n⚠️  Found {len(duplicate_queries)} duplicate queries:")
        for attr_type, query in duplicate_queries[:5]:
            logger.warning(f"  {attr_type.value}: {query}")
        if len(duplicate_queries) > 5:
            logger.warning(f"  ... and {len(duplicate_queries) - 5} more")
    else:
        logger.info("\n✅ No duplicate queries found")

    # Check query quality
    short_queries = []
    for attr_type in covered_templates:
        templates = config_loader.get_query_templates(attr_type)
        for template in templates:
            if len(template.split()) < 3:
                short_queries.append((attr_type, template))

    if short_queries:
        logger.warning(
            f"\n⚠️  Found {len(short_queries)} potentially short queries (< 3 words):"
        )
        for attr_type, query in short_queries[:5]:
            logger.warning(f"  {attr_type.value}: {query}")
    else:
        logger.info("✅ All queries have sufficient length")

    # Final summary
    logger.info(f"\n{'='*80}")
    logger.info("Summary")
    logger.info(f"{'='*80}")
    logger.info(f"✅ Coverage: {coverage_percent:.1f}%")
    logger.info(f"✅ Total queries: {len(all_queries)}")
    logger.info(
        f"✅ Avg queries per attribute: {len(all_queries) / len(covered_templates):.1f}"
    )

    if missing_templates:
        logger.warning(f"⚠️  {len(missing_templates)} attributes need templates")
        return False
    else:
        logger.info("✅ All attributes have RAG templates!")
        return True


def show_attribute_details(attribute_name: str):
    """Show detailed information about a specific attribute's queries.

    Args:
        attribute_name: Name of the attribute (e.g., 'nct_number')
    """
    try:
        attr_type = AttributeType(attribute_name)
    except ValueError:
        logger.error(f"Unknown attribute: {attribute_name}")
        logger.info(f"Available attributes: {[a.value for a in AttributeType][:10]}...")
        return

    config_loader = RAGConfigLoader()
    templates = config_loader.get_query_templates(attr_type)

    logger.info(f"\n{'='*80}")
    logger.info(f"Attribute: {attr_type.value}")
    logger.info(f"{'='*80}")

    if templates:
        logger.info(f"\nTotal queries: {len(templates)}")
        logger.info("\nQuery templates:")
        for i, template in enumerate(templates, 1):
            logger.info(f"  {i}. {template}")
    else:
        logger.warning(f"\n⚠️  No RAG templates found for {attr_type.value}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate RAG query templates")
    parser.add_argument(
        "--attribute",
        type=str,
        help="Show details for a specific attribute (e.g., 'nct_number')",
    )

    args = parser.parse_args()

    if args.attribute:
        show_attribute_details(args.attribute)
    else:
        success = validate_query_templates()
        sys.exit(0 if success else 1)
