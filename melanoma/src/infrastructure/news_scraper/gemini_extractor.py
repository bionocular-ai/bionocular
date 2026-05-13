import asyncio
import logging

from pydantic import BaseModel, Field

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

Return a JSON object with:
- nct_ids: array of NCT ID strings (empty array if none found)
- efficacy_data: object keyed by cancer type name, each value is an object of metric name to string value.
  Example: {{"Cutaneous Melanoma": {{"orr": "68%", "median_pfs": "12.3 months"}}, "Basal Cell Carcinoma": {{"orr": "45%"}}}}
  Only include cancer types that have efficacy data in this article. Omit types with no data.
- safety_data: same structure as efficacy_data but for safety metrics.
  Example: {{"Cutaneous Melanoma": {{"grade_3_plus_ae_pct": "23%", "serious_ae": "12%"}}}}
"""


class NewsExtractionResult(BaseModel):
    nct_ids: list[str] = Field(default_factory=list)
    has_efficacy: bool = False
    efficacy_data: dict[str, dict[str, str]] = Field(default_factory=dict)
    has_safety: bool = False
    safety_data: dict[str, dict[str, str]] = Field(default_factory=dict)


class GeminiNewsExtractor:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self._service = GeminiLLMService(api_key=api_key, model=model)

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
            result = asyncio.run(
                self._service.generate_structured(
                    prompt=prompt,
                    response_schema=NewsExtractionResult,
                    operation="news_extraction",
                    max_tokens=2048,
                )
            )
            result.has_efficacy = any(bool(v) for v in result.efficacy_data.values())
            result.has_safety = any(bool(v) for v in result.safety_data.values())
            return result
        except Exception as exc:
            logger.warning("Gemini extraction failed for %r: %s", title[:60], exc)
            return NewsExtractionResult()
