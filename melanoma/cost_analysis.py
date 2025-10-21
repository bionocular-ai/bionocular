"""Cost analysis script for enhanced extraction system.

This script demonstrates cost tracking and provides utilities for analyzing
the cost of running the enhanced extraction system.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

# Import after path modification
from src.app.enhanced_extraction_service import EnhancedExtractionService  # noqa: E402
from src.domain.extraction_models import AttributeType  # noqa: E402
from src.infrastructure.attribute_extractor import AttributeExtractor  # noqa: E402
from src.infrastructure.clinical_trials_api_service import (  # noqa: E402
    ClinicalTrialsAPIService,
)
from src.infrastructure.cost_calculator import CostCalculator, ModelType  # noqa: E402
from src.infrastructure.cost_tracking_llm_service import (  # noqa: E402
    CostTrackingLLMService,
)
from src.infrastructure.langchain.llm import LangChainLLMService  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def analyze_extraction_costs():
    """Analyze costs for different extraction scenarios."""

    print("🔍 Enhanced Extraction System - Cost Analysis")
    print("=" * 60)

    # Initialize cost calculator
    cost_calculator = CostCalculator(default_model=ModelType.GPT_4O_MINI)

    # Initialize LLM service with cost tracking
    llm_service = LangChainLLMService()
    cost_tracking_llm = CostTrackingLLMService(llm_service, cost_calculator)

    # Initialize other services (simplified for cost analysis)
    rag_provider = None  # Would be initialized in real scenario
    attribute_extractor = AttributeExtractor(cost_tracking_llm, None)
    api_service = ClinicalTrialsAPIService("data/doctorci.db")

    # Initialize enhanced extraction service
    _ = EnhancedExtractionService(
        treatment_arm_separator=None,  # Would be initialized in real scenario
        arm_aware_rag_provider=rag_provider,
        attribute_extractor=attribute_extractor,
        llm_service=cost_tracking_llm,
        clinical_trials_api_service=api_service,
    )

    # Test scenarios
    scenarios = [
        {
            "name": "Single Abstract - Basic Attributes",
            "attributes": [
                AttributeType.NCT_NUMBER,
                AttributeType.GENERIC_NAME,
                AttributeType.P_VALUE_OS,
                AttributeType.OBJECTIVE_RESPONSE_RATE,
                AttributeType.GRADE_3_PLUS_AE,
            ],
            "description": "Extract 5 basic attributes from a single abstract",
        },
        {
            "name": "Single Abstract - All Safety Attributes",
            "attributes": [
                AttributeType.AE,
                AttributeType.GRADE_3_PLUS_AE,
                AttributeType.AE_LEADING_TO_DISCONTINUATION,
                AttributeType.SERIOUS_AE,
                AttributeType.IMMUNE_RELATED_AE,
                AttributeType.SERIOUS_IMMUNE_RELATED_AE,
                AttributeType.AE_LEADING_TO_DEATH,
                AttributeType.TEAE,
                AttributeType.GRADE_3_PLUS_TEAE,
                AttributeType.GRADE_3_TEAE,
                AttributeType.GRADE_4_TEAE,
                AttributeType.GRADE_5_TEAE,
                AttributeType.TRAE,
                AttributeType.GRADE_3_PLUS_TRAE,
                AttributeType.CRS,
                AttributeType.WBC_DECREASED,
            ],
            "description": "Extract all safety-related attributes from a single abstract",
        },
        {
            "name": "Single Abstract - Complete Set",
            "attributes": list(AttributeType),  # All attributes
            "description": "Extract all 80+ attributes from a single abstract",
        },
    ]

    # Sample abstract for testing
    sample_abstract = """
    Background: This phase II study evaluated the efficacy and safety of pembrolizumab
    in patients with advanced melanoma.

    Methods: Patients with unresectable stage III/IV melanoma received pembrolizumab
    200 mg every 3 weeks. Primary endpoint was objective response rate (ORR) by RECIST v1.1.

    Results: Of 173 patients, 33% achieved objective response. Median progression-free
    survival was 5.5 months. Grade 3+ adverse events occurred in 15% of patients.

    Conclusions: Pembrolizumab demonstrated clinical activity in advanced melanoma with
    manageable toxicity.
    """

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n📊 Scenario {i}: {scenario['name']}")
        print(f"Description: {scenario['description']}")
        print(f"Attributes: {len(scenario['attributes'])}")
        print("-" * 40)

        # Reset cost calculator for this scenario
        cost_calculator.reset()

        # Estimate costs for this scenario
        total_estimated_cost = 0
        for attr in scenario["attributes"]:
            # Create a sample prompt for cost estimation
            sample_prompt = f"""
            TASK: Extract {attr.value} from the clinical trial abstract.

            ABSTRACT:
            {sample_abstract}

            Please extract the {attr.value} value and return only the numeric result.
            """

            # Estimate cost for this attribute
            cost_estimate = cost_calculator.estimate_cost_for_text(
                prompt_text=sample_prompt,
                estimated_completion_length=50,  # Short response expected
                model="gpt-4o-mini",
            )

            total_estimated_cost += cost_estimate["estimated_cost"]

        print(f"Estimated Cost: ${total_estimated_cost:.6f}")
        print(
            f"Cost per Attribute: ${total_estimated_cost / len(scenario['attributes']):.6f}"
        )

        # Show cost breakdown by model
        print(f"Model: {cost_estimate['model']}")
        print(
            f"Estimated Tokens per Attribute: {cost_estimate['estimated_total_tokens']}"
        )

    print("\n" + "=" * 60)
    print("💡 Cost Optimization Recommendations")
    print("=" * 60)

    recommendations = [
        "1. Use file path extraction for Conference and Published Year (no LLM cost)",
        "2. Use Clinical Trials API for non-numeric attributes (no LLM cost)",
        "3. Use direct propagation for NCT Number and Generic Name (no LLM cost)",
        "4. Batch similar attributes in single LLM calls when possible",
        "5. Use gpt-4o-mini for most extractions (10x cheaper than gpt-4o)",
        "6. Implement caching for repeated extractions",
        "7. Use backbone prompts only for complex attributes that need them",
        "8. Consider parallel processing for multiple abstracts",
    ]

    for rec in recommendations:
        print(rec)

    print("\n" + "=" * 60)
    print("📈 Cost Scaling Analysis")
    print("=" * 60)

    # Cost scaling analysis
    abstracts_count = [1, 10, 100, 1000]
    attributes_per_abstract = 20  # Average number of attributes

    print(
        f"{'Abstracts':<10} {'Total Attributes':<15} {'Estimated Cost':<15} {'Cost per Abstract':<18}"
    )
    print("-" * 70)

    for count in abstracts_count:
        total_attributes = count * attributes_per_abstract
        estimated_cost = count * 0.05  # Rough estimate: $0.05 per abstract
        cost_per_abstract = estimated_cost / count if count > 0 else 0

        print(
            f"{count:<10} {total_attributes:<15} ${estimated_cost:<14.2f} ${cost_per_abstract:<17.4f}"
        )

    print("\n" + "=" * 60)
    print("🎯 Model Comparison")
    print("=" * 60)

    # Model comparison
    models = [
        ("gpt-4o-mini", 0.15, 0.60),
        ("gpt-4o", 2.50, 10.00),
        ("gpt-4-turbo", 10.00, 30.00),
    ]

    sample_tokens = 1000  # 1K prompt + 1K completion

    print(
        f"{'Model':<15} {'Prompt Cost':<12} {'Completion Cost':<15} {'Total Cost':<12}"
    )
    print("-" * 60)

    for model, prompt_rate, completion_rate in models:
        prompt_cost = (sample_tokens / 1_000_000) * prompt_rate
        completion_cost = (sample_tokens / 1_000_000) * completion_rate
        total_cost = prompt_cost + completion_cost

        print(
            f"{model:<15} ${prompt_cost:<11.6f} ${completion_cost:<14.6f} ${total_cost:<11.6f}"
        )

    print("\n✅ Cost analysis complete!")


async def estimate_batch_processing_costs():
    """Estimate costs for batch processing multiple abstracts."""

    print("\n🔄 Batch Processing Cost Estimation")
    print("=" * 50)

    cost_calculator = CostCalculator()

    # Simulate batch processing
    batch_sizes = [1, 5, 10, 25, 50, 100]
    attributes_per_abstract = 20

    print(
        f"{'Batch Size':<12} {'Total Attributes':<15} {'Estimated Cost':<15} {'Cost per Abstract':<18}"
    )
    print("-" * 70)

    for batch_size in batch_sizes:
        total_attributes = batch_size * attributes_per_abstract

        # Estimate cost per abstract (rough calculation)
        # Assuming average 2K tokens per attribute extraction
        tokens_per_attribute = 2000
        total_tokens = total_attributes * tokens_per_attribute

        # Calculate cost using gpt-4o-mini pricing
        prompt_tokens = total_tokens // 2
        completion_tokens = total_tokens // 2

        cost = cost_calculator.calculate_cost(
            prompt_tokens, completion_tokens, "gpt-4o-mini"
        )
        cost_per_abstract = cost / batch_size if batch_size > 0 else 0

        print(
            f"{batch_size:<12} {total_attributes:<15} ${cost:<14.2f} ${cost_per_abstract:<17.4f}"
        )


def create_cost_report_template():
    """Create a template for cost reporting."""

    template = {
        "extraction_session": {
            "timestamp": datetime.now().isoformat(),
            "abstracts_processed": 0,
            "total_attributes_extracted": 0,
            "total_cost": 0.0,
            "cost_per_abstract": 0.0,
            "cost_per_attribute": 0.0,
        },
        "breakdown": {
            "by_operation": {
                "arm_separation": {"calls": 0, "cost": 0.0},
                "attribute_extraction": {"calls": 0, "cost": 0.0},
                "backbone_prompt": {"calls": 0, "cost": 0.0},
                "file_path_extraction": {"calls": 0, "cost": 0.0},
                "api_lookup": {"calls": 0, "cost": 0.0},
            },
            "by_attribute_type": {},
            "by_model": {},
        },
        "optimization_suggestions": [
            "Consider using file path extraction for Conference/Year",
            "Use API lookups for non-numeric attributes",
            "Batch similar extractions together",
            "Implement caching for repeated operations",
        ],
    }

    # Save template
    with open("cost_report_template.json", "w") as f:
        json.dump(template, f, indent=2)

    print("📄 Cost report template created: cost_report_template.json")


if __name__ == "__main__":
    print("🚀 Starting Enhanced Extraction Cost Analysis...")

    # Run cost analysis
    asyncio.run(analyze_extraction_costs())

    # Run batch processing estimation
    asyncio.run(estimate_batch_processing_costs())

    # Create cost report template
    create_cost_report_template()

    print("\n🎉 Cost analysis complete!")
    print("\nTo track costs in your extraction runs:")
    print("1. Use CostTrackingLLMService wrapper around your LLM service")
    print("2. Call print_cost_summary() after extraction")
    print("3. Use save_cost_report() to save detailed reports")
    print("4. Monitor costs with get_cost_summary()")
