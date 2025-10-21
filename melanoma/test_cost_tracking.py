"""Test script for cost tracking functionality."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

# Import after path modification
from src.infrastructure.cost_calculator import CostCalculator, ModelType  # noqa: E402
from src.infrastructure.cost_tracking_llm_service import (  # noqa: E402
    CostTrackingLLMService,
)
from src.infrastructure.langchain.llm import LangChainLLMService  # noqa: E402


async def test_cost_tracking():
    """Test cost tracking functionality."""

    print("🧪 Testing Cost Tracking Functionality")
    print("=" * 50)

    # Initialize cost calculator
    cost_calculator = CostCalculator(default_model=ModelType.GPT_4O_MINI)

    # Initialize LLM service with cost tracking
    llm_service = LangChainLLMService()
    cost_tracking_llm = CostTrackingLLMService(llm_service, cost_calculator)

    # Test scenarios
    test_prompts = [
        {
            "prompt": "What is the capital of France?",
            "operation": "simple_question",
            "attribute_type": None,
        },
        {
            "prompt": "Extract the NCT number from this clinical trial abstract: NCT12345678",
            "operation": "attribute_extraction",
            "attribute_type": "nct_number",
        },
        {
            "prompt": "Classify this therapy type: pembrolizumab",
            "operation": "therapy_classification",
            "attribute_type": "type_of_therapy",
        },
    ]

    print("Running test prompts...")

    for i, test in enumerate(test_prompts, 1):
        print(f"\nTest {i}: {test['operation']}")
        try:
            response = await cost_tracking_llm.generate_text(
                prompt=test["prompt"],
                operation=test["operation"],
                attribute_type=test["attribute_type"],
            )
            print(f"Response: {response[:100]}...")
        except Exception as e:
            print(f"Error: {e}")

    # Print cost summary
    print(f"\n{'='*50}")
    print("COST SUMMARY")
    print(f"{'='*50}")
    cost_tracking_llm.print_cost_summary()

    # Save detailed report
    cost_tracking_llm.save_cost_report("test_cost_report.json")
    print("\n✅ Detailed cost report saved to: test_cost_report.json")

    # Test cost estimation
    print(f"\n{'='*50}")
    print("COST ESTIMATION")
    print(f"{'='*50}")

    sample_prompt = """
    TASK: Extract the objective response rate from this clinical trial abstract.

    ABSTRACT:
    This phase II study evaluated pembrolizumab in 100 patients with advanced melanoma.
    The objective response rate was 35% (35/100 patients).

    Please extract the objective response rate percentage.
    """

    estimate = cost_calculator.estimate_cost_for_text(
        prompt_text=sample_prompt, estimated_completion_length=50
    )

    print(f"Model: {estimate['model']}")
    print(f"Prompt tokens: {estimate['prompt_tokens']}")
    print(f"Estimated completion tokens: {estimate['estimated_completion_tokens']}")
    print(f"Estimated total tokens: {estimate['estimated_total_tokens']}")
    print(f"Estimated cost: ${estimate['estimated_cost']:.6f}")

    print("\n✅ Cost tracking test complete!")


if __name__ == "__main__":
    asyncio.run(test_cost_tracking())
