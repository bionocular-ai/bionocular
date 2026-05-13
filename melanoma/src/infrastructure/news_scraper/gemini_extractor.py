import asyncio
import logging
from typing import Optional

from pydantic import BaseModel, Field

from ..cost_calculator import CostCalculator
from ..gemini_service import GeminiLLMService

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """You are a clinical data extractor for oncology news articles.

Article Title: {title}
Cancer types covered by this article: {cancer_types}

Article Text:
{full_text}

Extract:
1. NCT IDs: Any clinical trial registration numbers (format: NCTxxxxxxxx, e.g. NCT12345678).
2. For each cancer type listed above, extract any reported data:
   - Efficacy metrics: ORR, PFS, OS, DOR, hazard ratios, p-values, response rates, survival rates
   - Safety metrics: AE rates, Grade 3+ adverse events, serious AEs, TRAEs, discontinuation rates

Return ONLY valid JSON, no prose, no markdown fences. JSON structure:
{{
  "nct_ids": ["NCT12345678"],
  "efficacy_data": {{"Cutaneous Melanoma": {{"orr": "68%", "median_pfs": "12.3 months"}}}},
  "safety_data": {{"Cutaneous Melanoma": {{"grade_3_plus_ae_pct": "23%"}}}}
}}
- nct_ids: array of NCT ID strings (empty array if none found)
- efficacy_data: object keyed by cancer type name, each value is metric name to string value. Omit cancer types with no data.
- safety_data: same structure as efficacy_data but for safety metrics. Omit cancer types with no data.
"""


class NewsExtractionResult(BaseModel):
    nct_ids: list[str] = Field(default_factory=list)
    has_efficacy: bool = False
    efficacy_data: dict[str, dict[str, str]] = Field(default_factory=dict)
    has_safety: bool = False
    safety_data: dict[str, dict[str, str]] = Field(default_factory=dict)


class GeminiNewsExtractor:
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        cost_calculator: Optional[CostCalculator] = None,
    ) -> None:
        self._service = GeminiLLMService(
            api_key=api_key, model=model, cost_calculator=cost_calculator
        )
        self.cost_calculator = cost_calculator

    def extract(
        self, title: str, full_text: str, cancer_types: list[str]
    ) -> NewsExtractionResult:
        capped = full_text[:40000] if len(full_text) > 40000 else full_text
        cancer_types_str = ", ".join(cancer_types) if cancer_types else "unknown"
        prompt = _EXTRACTION_PROMPT.format(
            title=title,
            cancer_types=cancer_types_str,
            full_text=capped,
        )
        try:
            raw = asyncio.run(
                self._service.extract_json(
                    prompt=prompt,
                    operation="news_extraction",
                )
            )
            result = NewsExtractionResult.model_validate(raw)
            result.has_efficacy = any(bool(v) for v in result.efficacy_data.values())
            result.has_safety = any(bool(v) for v in result.safety_data.values())
            return result
        except Exception as exc:
            logger.warning("Gemini extraction failed for %r: %s", title[:60], exc)
            return NewsExtractionResult()
