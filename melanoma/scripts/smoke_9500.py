"""Smoke test: extract one ASCO 2026 abstract (#9500, KEYNOTE-942) end to end.

Touches none of the pipeline outputs - the result goes to data/smoke/.

    cd melanoma && poetry run python3 scripts/smoke_9500.py [abstract_id]
"""

import asyncio
import os
import sys
from pathlib import Path

_MELANOMA_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_MELANOMA_ROOT))

from run_abstract_pipeline import (  # noqa: E402
    ABSTRACT_ATTRIBUTES,
    DocumentType,
    _save_results,
    _serialize_result,
    build_services,
    logger,
)

ABSTRACT_FILE = _MELANOMA_ROOT / "data/postprocessed/ASCO_Abstracts/ASCO_2026.md"
OUTPUT_FILE = _MELANOMA_ROOT / "data/smoke/smoke_9500_result.json"


def load_abstract(abstract_id: str) -> str:
    """Return the single abstract block whose ID line matches abstract_id."""
    for block in ABSTRACT_FILE.read_text(encoding="utf-8").split("### Abstract ID:")[1:]:
        if block.strip().split("\n")[0].strip() == abstract_id:
            return "### Abstract ID:" + block
    raise SystemExit(f"Abstract {abstract_id} not found in {ABSTRACT_FILE}")


async def main() -> None:
    abstract_id = sys.argv[1] if len(sys.argv) > 1 else "9500"
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        raise SystemExit("GOOGLE_API_KEY is not set in the environment")

    text = load_abstract(abstract_id)
    extraction_service, cost_calculator = build_services(api_key)

    full_id = f"ASCO_2026_{abstract_id}"
    result = await extraction_service.extract(text, full_id, DocumentType.ABSTRACT)

    _save_results(
        OUTPUT_FILE,
        [_serialize_result(result, {"abstract_id": full_id}, ABSTRACT_ATTRIBUTES)],
        {"conference": "ASCO", "year": 2026, "smoke": True},
    )

    logger.info(f"Arms: {len(result.arm_results)}")
    logger.info(f"Attributes extracted: {result.total_attributes_extracted}")
    logger.info(f"Confidence: {result.overall_confidence:.2f}")
    logger.info(f"Wrote {OUTPUT_FILE}")
    cost_calculator.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
