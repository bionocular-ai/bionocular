"""Enhanced extraction service with comprehensive attribute support.

This service integrates RAG-enhanced extraction with Clinical Trials API
data for comprehensive clinical trial data extraction.

Two extraction paths are supported:

* The new family-grouped path (default), driven by
  :class:`FamilyExtractor` + verifier + drug enricher with Gemini context
  caching.
* The legacy RAG + per-attribute path, kept behind the
  ``USE_LEGACY_RAG_EXTRACTION`` env flag for fallback during the rollout.
"""

import asyncio
import logging
import os
import re
from datetime import datetime
from typing import Any, Optional, cast

from ..domain.extraction_interfaces import AttributeExtractor, LLMService
from ..domain.extraction_models import (
    FAMILY_TO_ATTRIBUTES,
    AttributeConfigurationFactory,
    AttributeFamily,
    AttributeType,
    ExtractedAttribute,
    ValidationStatus,
)
from ..domain.models import DocumentType
from ..domain.prompt_templates import SHARED_EXTRACTION_RULES
from ..domain.treatment_arm_models import (
    ArmSpecificContext,
    TreatmentArm,
    TreatmentArmExtractionResult,
    TreatmentArmSeparationResult,
)
from ..infrastructure.arm_aware_rag_provider import ArmAwareRAGContextProvider
from ..infrastructure.batch_attribute_extractor import BatchAttributeExtractor
from ..infrastructure.clinical_trials_api_service import ClinicalTrialsAPIService
from ..infrastructure.cost_calculator import CostCalculator
from ..infrastructure.cost_tracking_llm_service import CostTrackingLLMService
from ..infrastructure.drug_enricher import enrich_result
from ..infrastructure.family_extractor import FamilyExtractor
from ..infrastructure.family_section_router import slice_for_family
from ..infrastructure.file_path_extractor import FilePathExtractor
from ..infrastructure.gemini_service import GeminiLLMService
from ..infrastructure.markdown_section_parser import SectionCategory, parse_markdown
from ..infrastructure.prompt_templates import ExtractionPromptTemplateProvider
from ..infrastructure.treatment_arm_separator import TreatmentArmSeparator
from ..infrastructure.value_validator import validate_for_attribute
from ..infrastructure.verifier import verify_low_confidence

logger = logging.getLogger(__name__)


# ── Module constants ─────────────────────────────────────────────────────────
def _parse_metadata_section(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


_CONFERENCE_DOC_ID_RE = re.compile(r"^(ASCO|ESMO)_(\d{4})", re.IGNORECASE)


def _parse_conference_from_doc_id(doc_id: str) -> dict[str, str]:
    m = _CONFERENCE_DOC_ID_RE.match(doc_id)
    if not m:
        return {}
    return {"conference": m.group(1).upper(), "published_year": m.group(2)}


PROMPT_VERSION = "v2.0"
LEGACY_FLAG_ENV = "USE_LEGACY_RAG_EXTRACTION"
LEGACY_FLAG_ENABLED_VALUE = "1"

_ABSTRACT_EXCLUDED_FAMILIES: frozenset[AttributeFamily] = frozenset()


class EnhancedExtractionService:
    """Enhanced extraction service with comprehensive attribute support.

    This service orchestrates the complete workflow of:
    1. Treatment arm separation
    2. RAG context retrieval per arm
    3. Clinical Trials API data integration
    4. Targeted attribute extraction per arm
    5. Quality assessment and validation
    """

    def __init__(
        self,
        treatment_arm_separator: TreatmentArmSeparator,
        arm_aware_rag_provider: Optional[ArmAwareRAGContextProvider] = None,
        attribute_extractor: Optional[AttributeExtractor] = None,
        llm_service: Optional[LLMService] = None,
        clinical_trials_api_service: Optional[ClinicalTrialsAPIService] = None,
        enable_cost_tracking: bool = True,
        max_concurrent_attributes: int = 20,
        family_extractor: Optional[FamilyExtractor] = None,
        gemini: Optional[GeminiLLMService] = None,
    ):
        """Initialize enhanced extraction service.

        Both extraction paths share the treatment arm separator. The legacy
        deps (``arm_aware_rag_provider``, ``attribute_extractor``,
        ``llm_service``) are optional so a deployment can wire only the new
        path; if the legacy flag is set without those deps, ``extract`` raises.

        Args:
            treatment_arm_separator: Service for separating treatment arms
            arm_aware_rag_provider: Legacy RAG provider for arm-aware context
            attribute_extractor: Legacy per-attribute LLM extractor
            llm_service: LLM service used by the legacy path
            clinical_trials_api_service: Service for Clinical Trials API data
            enable_cost_tracking: Whether to enable cost tracking on the
                legacy LLM service
            max_concurrent_attributes: Max simultaneous LLM attribute requests
                in the legacy per-attribute path
            family_extractor: New-path family-grouped extractor
            gemini: New-path Gemini service used for context caching and
                verifier calls
        """
        self.treatment_arm_separator = treatment_arm_separator
        self.arm_aware_rag_provider = arm_aware_rag_provider
        self.attribute_extractor = attribute_extractor
        self.clinical_trials_api_service = clinical_trials_api_service
        self.max_concurrent_attributes = max_concurrent_attributes

        # New-path deps.
        self.family_extractor = family_extractor
        self.gemini = gemini

        # Set up cost tracking if enabled (only meaningful when legacy
        # llm_service is wired).
        if enable_cost_tracking and llm_service is not None:
            self.cost_calculator = CostCalculator()
            self.llm_service: Optional[LLMService] = CostTrackingLLMService(
                llm_service, self.cost_calculator
            )
            self.cost_tracking_enabled = True
        else:
            self.llm_service = llm_service
            self.cost_calculator = None
            self.cost_tracking_enabled = False

        # Initialize providers
        self.prompt_provider = ExtractionPromptTemplateProvider()
        self.file_path_extractor = FilePathExtractor()

        # Get preferred model from environment or use default
        preferred_model = os.getenv("EXTRACTION_MODEL", "gpt-4o")

        self.batch_extractor: Optional[BatchAttributeExtractor] = (
            BatchAttributeExtractor(
                cast(CostTrackingLLMService, self.llm_service),
                self.prompt_provider,
                preferred_model=preferred_model,
            )
            if self.llm_service is not None
            else None
        )

        # Get attribute configurations
        self.attribute_configs = AttributeConfigurationFactory.get_all_configurations()
        self.api_sourced_attributes = (
            AttributeConfigurationFactory.get_api_sourced_attributes()
        )

        logger.info("Enhanced extraction service initialized")

        if self.cost_tracking_enabled:
            logger.info("Cost tracking enabled")

    # ------------------------------------------------------------------ #
    # New family-grouped extraction entry point
    # ------------------------------------------------------------------ #

    async def extract(
        self,
        doc_text: str,
        doc_id: str,
        doc_type: DocumentType,
    ) -> TreatmentArmExtractionResult:
        """Extract attributes from ``doc_text`` using the new family-grouped path.

        Routes to the legacy RAG path when ``USE_LEGACY_RAG_EXTRACTION=1`` is
        set in the environment. The new path: separates arms once, runs all
        applicable family extractions concurrently against a single Gemini
        context cache, deterministically validates each value, sends low-
        confidence values through the verifier, then enriches the assembled
        result with drug-knowledge-derived MODALITY / TARGET attributes.
        """
        if os.getenv(LEGACY_FLAG_ENV) == LEGACY_FLAG_ENABLED_VALUE:
            return await self._legacy_rag_extract(doc_text, doc_id, doc_type)

        if self.family_extractor is None or self.gemini is None:
            raise RuntimeError(
                "EnhancedExtractionService new-path requires both "
                "`family_extractor` and `gemini` to be provided. Either "
                f"wire them in the constructor or set {LEGACY_FLAG_ENV}=1 "
                "to use the legacy RAG path."
            )

        start_time = datetime.now()
        cache_id = await self.gemini.create_context_cache(
            doc_text, system_instruction=SHARED_EXTRACTION_RULES
        )
        try:
            arm_result = await self.treatment_arm_separator.separate_treatment_arms(
                doc_text, doc_id
            )
            arms = arm_result.treatment_arms
            if not arms:
                logger.warning(
                    "No treatment arms identified for %s — returning empty result",
                    doc_id,
                )
                processing_time = int(
                    (datetime.now() - start_time).total_seconds() * 1000
                )
                return TreatmentArmExtractionResult(
                    abstract_id=doc_id,
                    arm_results={},
                    overall_confidence=0.0,
                    processing_time_ms=processing_time,
                    errors=["No treatment arms identified"],
                    prompt_version=PROMPT_VERSION,
                )

            arms_by_id = {a.arm_id: a for a in arms}
            per_arm: dict[str, dict[AttributeType, ExtractedAttribute]] = {
                a.arm_id: {} for a in arms
            }
            pub_meta: dict[str, str] = {}

            if doc_type == DocumentType.ABSTRACT:
                families = self._families_for_doc_type(doc_type)
                family_inputs: dict[AttributeFamily, str] = {
                    f: doc_text for f in families
                }
            else:
                parsed = parse_markdown(doc_text)
                pub_meta = _parse_metadata_section(
                    parsed.text_for(SectionCategory.METADATA)
                )
                if parsed.unclassified:
                    logger.info(
                        "section_parser_unclassified doc_id=%s headers=%s",
                        doc_id,
                        parsed.unclassified[:10],
                    )
                candidate_families = self._families_for_doc_type(doc_type)
                family_inputs = {}
                skipped: list[str] = []
                for fam in candidate_families:
                    sliced = slice_for_family(fam, parsed, raw_md=doc_text)
                    if sliced is None:
                        skipped.append(fam.value)
                    else:
                        family_inputs[fam] = sliced
                if skipped:
                    logger.info(
                        "section_route_skipped doc_id=%s skipped=%s", doc_id, skipped
                    )
                families = tuple(family_inputs.keys())

            family_results = await asyncio.gather(
                *[
                    self.family_extractor.extract(
                        cache_id, family_inputs[fam], fam, arms
                    )
                    for fam in families
                ]
            )
            for fr in family_results:
                for arm_id, attrs in fr.items():
                    if arm_id in per_arm:
                        per_arm[arm_id].update(attrs)

            # NUMBER_OF_PATIENTS comes from the arm separator, not the LLM.
            for arm in arms:
                n = arm.patient_count
                per_arm[arm.arm_id][
                    AttributeType.NUMBER_OF_PATIENTS
                ] = ExtractedAttribute(
                    attribute_type=AttributeType.NUMBER_OF_PATIENTS,
                    value=str(n) if n else "",
                    source_quote="",
                    confidence=1.0 if n else 0.0,
                    source="arm_separator",
                    validation_status=ValidationStatus.VALID
                    if n
                    else ValidationStatus.EMPTY,
                )
                # PDF_NUMBER is the document filename — never extracted by LLM.
                per_arm[arm.arm_id][AttributeType.PDF_NUMBER] = ExtractedAttribute(
                    attribute_type=AttributeType.PDF_NUMBER,
                    value=doc_id,
                    source_quote="",
                    confidence=1.0,
                    source="file_path",
                    validation_status=ValidationStatus.VALID,
                )
                # PUBLICATION_NAME / PUBLICATION_YEAR from injected # Metadata section.
                for attr_type, meta_key in (
                    (AttributeType.PUBLICATION_NAME, "citation"),
                    (AttributeType.PUBLICATION_YEAR, "year"),
                ):
                    val = pub_meta.get(meta_key, "")
                    per_arm[arm.arm_id][attr_type] = ExtractedAttribute(
                        attribute_type=attr_type,
                        value=val,
                        source_quote="",
                        confidence=1.0 if val else 0.0,
                        source="metadata_section",
                        validation_status=ValidationStatus.VALID
                        if val
                        else ValidationStatus.EMPTY,
                    )
                # CONFERENCE / PUBLISHED_YEAR from doc_id (e.g. ASCO_2024).
                conf_meta = _parse_conference_from_doc_id(doc_id)
                for attr_type, meta_key in (
                    (AttributeType.CONFERENCE, "conference"),
                    (AttributeType.PUBLISHED_YEAR, "published_year"),
                ):
                    val = conf_meta.get(meta_key, "")
                    per_arm[arm.arm_id][attr_type] = ExtractedAttribute(
                        attribute_type=attr_type,
                        value=val,
                        source_quote="",
                        confidence=1.0 if val else 0.0,
                        source="file_path",
                        validation_status=ValidationStatus.VALID
                        if val
                        else ValidationStatus.EMPTY,
                    )

            # Validate-then-verify pass.
            for arm_id, attrs in per_arm.items():
                for attr_type, extracted in list(attrs.items()):
                    raw_value = extracted.value if extracted.value is not None else ""
                    ok, normalized, reason = validate_for_attribute(
                        attr_type, str(raw_value)
                    )
                    if ok:
                        extracted.value = normalized
                        extracted.validation_status = ValidationStatus.VALID
                    else:
                        attrs[attr_type] = await verify_low_confidence(
                            self.gemini,
                            cache_id,
                            doc_text,
                            arms_by_id[arm_id],
                            attr_type,
                            str(raw_value),
                            reason,
                        )

            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            result = self._assemble_result(
                doc_id=doc_id,
                arms=arms,
                per_arm=per_arm,
                processing_time_ms=processing_time,
                prompt_version=PROMPT_VERSION,
            )
            return enrich_result(result)
        finally:
            await self.gemini.delete_cache(cache_id)

    def _families_for_doc_type(
        self, doc_type: DocumentType
    ) -> tuple[AttributeFamily, ...]:
        """Return the families to extract for a given document type.

        Abstracts skip ``EFS_RFS_MFS`` and ``TIME_TO_METRICS`` (rarely
        reported in conference abstracts). Publications get all 12 families.
        """
        all_families = tuple(FAMILY_TO_ATTRIBUTES.keys())
        if doc_type == DocumentType.ABSTRACT:
            return tuple(
                f for f in all_families if f not in _ABSTRACT_EXCLUDED_FAMILIES
            )
        return all_families

    def _assemble_result(
        self,
        doc_id: str,
        arms: list[TreatmentArm],
        per_arm: dict[str, dict[AttributeType, ExtractedAttribute]],
        processing_time_ms: int,
        prompt_version: str,
    ) -> TreatmentArmExtractionResult:
        """Build a :class:`TreatmentArmExtractionResult` from the new-path data.

        Mirrors the JSON shape produced by ``extract_attributes_from_abstract_batch``
        so downstream serializers and the drug-enricher work unchanged.
        """
        arm_results: dict[str, dict[str, Any]] = {}
        total_attributes = 0

        for arm in arms:
            attrs_for_arm = per_arm.get(arm.arm_id, {})
            attribute_dicts: dict[str, dict[str, Any]] = {}
            for attr_type, extracted in attrs_for_arm.items():
                attribute_dicts[attr_type.value] = {
                    "value": extracted.value,
                    "confidence": extracted.confidence,
                    "validation_status": (
                        extracted.validation_status.value
                        if hasattr(extracted.validation_status, "value")
                        else str(extracted.validation_status)
                    ),
                    "source_chunks": list(extracted.source_chunks),
                    "source": extracted.source,
                }
                if str(extracted.value or "").strip():
                    total_attributes += 1

            arm_results[arm.arm_id] = {
                "arm_id": arm.arm_id,
                "arm_name": arm.arm_name,
                "generic_name": arm.generic_name,
                "brand_name": arm.brand_name,
                "dose": arm.dose,
                "dosing_schedule": arm.dosing_schedule,
                "patient_count": arm.patient_count,
                "line_of_treatment": (
                    arm.line_of_treatment.value
                    if hasattr(arm.line_of_treatment, "value")
                    else arm.line_of_treatment
                ),
                "arm_type": (
                    arm.arm_type.value
                    if hasattr(arm.arm_type, "value")
                    else arm.arm_type
                ),
                "combination_drugs": arm.combination_drugs,
                "confidence_score": arm.confidence_score,
                "source_text": arm.source_text,
                "attributes": attribute_dicts,
                "errors": [],
                "warnings": [],
                "total_attributes": sum(
                    1
                    for a in attribute_dicts.values()
                    if str(a.get("value") or "").strip()
                ),
                "api_attributes": 0,
                "abstract_attributes": sum(
                    1
                    for a in attribute_dicts.values()
                    if str(a.get("value") or "").strip()
                ),
            }

        confidences = [
            a["confidence"]
            for arm_result in arm_results.values()
            for a in arm_result["attributes"].values()
            if isinstance(a, dict) and "confidence" in a
        ]
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return TreatmentArmExtractionResult(
            abstract_id=doc_id,
            arm_results=arm_results,
            overall_confidence=overall_confidence,
            processing_time_ms=processing_time_ms,
            total_attributes_extracted=total_attributes,
            prompt_version=prompt_version,
        )

    async def _legacy_rag_extract(
        self,
        doc_text: str,
        doc_id: str,
        doc_type: DocumentType,
    ) -> TreatmentArmExtractionResult:
        """Legacy entry-point: delegate to the existing per-attribute RAG path.

        Preserved verbatim behaviour by routing through
        :meth:`extract_attributes_from_abstract_batch`. The legacy path
        derives publication vs. abstract from heuristics on the text /
        file path, so ``doc_type`` is informational only.
        """
        del doc_type  # behaviour preserved by the legacy heuristics
        logger.warning(
            "Legacy RAG extraction path used — scheduled for removal 2026-08-04"
        )
        if self.batch_extractor is None or self.arm_aware_rag_provider is None:
            raise RuntimeError(
                f"{LEGACY_FLAG_ENV}=1 was set but the legacy dependencies "
                "(arm_aware_rag_provider, attribute_extractor, llm_service) "
                "are not wired into EnhancedExtractionService."
            )
        # Use the comprehensive set of attributes the legacy path already
        # supports — callers wishing a smaller set should use the legacy
        # API directly.
        attributes = list(self.attribute_configs.keys())
        return await self.extract_attributes_from_abstract_batch(
            abstract_text=doc_text,
            abstract_id=doc_id,
            attributes=attributes,
        )

    # ------------------------------------------------------------------ #
    # Legacy detection helpers (used by both paths' arm separation step)
    # ------------------------------------------------------------------ #

    def _is_publication(self, content: str, file_path: Optional[str] = None) -> bool:
        """Detect if content is a full publication (not an abstract).

        Args:
            content: Document content
            file_path: Optional file path for pattern matching

        Returns:
            True if this appears to be a publication
        """
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

    def _extract_results_section(self, content: str) -> Optional[str]:
        """Extract the Results section from publication content.

        For publications, treatment arms are typically described in the Results section,
        not in Background or Methods. This method extracts only the Results section
        for arm separation.

        Args:
            content: Full publication content

        Returns:
            Results section content, or None if not found
        """
        lines = content.split("\n")
        results_start = None
        results_end = None

        # Keywords that indicate Results section (prioritize more specific patterns first)
        # Order matters: more specific patterns should come first
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
        # or the one with more specific pattern (lower pattern_idx = more specific)
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
                for start_line, _pattern_idx, line_text in potential_starts:
                    if methods_line is not None and start_line > methods_line:
                        results_start = start_line
                        logger.debug(
                            f"Found Results section start at line {start_line} (after Methods): {line_text[:50]}"
                        )
                        break
                # If none found after Methods, use the most specific one
                if results_start is None:
                    potential_starts.sort(
                        key=lambda x: (x[0], x[1])
                    )  # Sort by line number, then pattern specificity
                    results_start = potential_starts[0][0]
                    logger.debug(
                        f"Found Results section start at line {results_start}: {potential_starts[0][2][:50]}"
                    )
            else:
                # No Methods section found, use the most specific pattern
                potential_starts.sort(
                    key=lambda x: (x[1], x[0])
                )  # Sort by pattern specificity, then line number
                results_start = potential_starts[0][0]
                logger.debug(
                    f"Found Results section start at line {results_start}: {potential_starts[0][2][:50]}"
                )

        # Second pass: find the end of the Results section
        if results_start is not None:
            for i in range(results_start + 1, len(lines)):
                line_stripped = lines[i].strip()
                for pattern in end_keywords:
                    if re.match(pattern, line_stripped, re.IGNORECASE):
                        results_end = i
                        logger.debug(
                            f"Found Results section end at line {i}: {line_stripped[:50]}"
                        )
                        break

                if results_end is not None:
                    break

        # If we found start but no end, Results section goes to end of document
        if results_start is not None and results_end is None:
            results_end = len(lines)

        if results_start is not None:
            if results_start is not None and results_end is not None:
                results_content = "\n".join(lines[results_start:results_end])
                logger.info(
                    f"Extracted Results section: {results_end - results_start} lines"
                )
            else:
                results_content = ""
                logger.warning("Results section boundaries not found")
            return results_content

        logger.warning("Results section not found in publication content")
        return None

    async def extract_attributes_from_abstract(
        self,
        abstract_text: str,
        abstract_id: str,
        attributes: list[AttributeType],
        context_chunks_per_arm: int = 5,
        similarity_threshold: float = 0.1,
        include_api_data: bool = True,
        file_path: Optional[str] = None,
    ) -> TreatmentArmExtractionResult:
        """Extract attributes from abstract using enhanced workflow.

        Args:
            abstract_text: Full abstract text
            abstract_id: Abstract identifier
            attributes: List of attributes to extract
            context_chunks_per_arm: Number of context chunks per arm
            similarity_threshold: Similarity threshold for RAG retrieval
            include_api_data: Whether to include Clinical Trials API data
            file_path: Optional file path for Conference/Year extraction

        Returns:
            Treatment arm extraction result
        """
        assert self.arm_aware_rag_provider is not None  # legacy path
        assert self.attribute_extractor is not None  # legacy path
        assert self.batch_extractor is not None  # legacy path
        start_time = datetime.now()

        try:
            logger.info(f"Starting enhanced extraction for abstract {abstract_id}")

            # Store file path for use in arm extraction
            self._current_file_path = file_path

            # Step 1: Separate treatment arms
            # For publications, extract Results section first and separate arms from it only
            is_pub = self._is_publication(abstract_text, file_path)
            text_for_arm_separation = abstract_text

            if is_pub:
                logger.info(
                    "Detected publication - extracting Results section for arm separation"
                )
                results_section = self._extract_results_section(abstract_text)
                if results_section:
                    text_for_arm_separation = results_section
                    logger.info(
                        f"Using Results section for arm separation ({len(results_section)} chars)"
                    )
                else:
                    logger.warning(
                        "Results section not found, using full publication text for arm separation"
                    )

            logger.info("Step 1: Separating treatment arms")
            separation_result = (
                await self.treatment_arm_separator.separate_treatment_arms(
                    text_for_arm_separation, abstract_id
                )
            )

            if not separation_result.treatment_arms:
                logger.warning(
                    f"No treatment arms identified for abstract {abstract_id}"
                )
                return TreatmentArmExtractionResult(
                    abstract_id=abstract_id,
                    arm_results={},
                    overall_confidence=0.0,
                    processing_time_ms=int(
                        (datetime.now() - start_time).total_seconds() * 1000
                    ),
                    errors=["No treatment arms identified"],
                )

            logger.info(
                f"Identified {len(separation_result.treatment_arms)} treatment arms"
            )

            # Step 2: Extract attributes for each treatment arm
            logger.info("Step 2: Extracting attributes per treatment arm")
            arm_results = {}
            total_attributes_extracted = 0

            for arm in separation_result.treatment_arms:
                try:
                    logger.info(f"Processing arm: {arm.arm_name}")

                    # Get RAG context for this arm
                    arm_context = (
                        await self.arm_aware_rag_provider.get_context_for_arm_attribute(
                            arm=arm,
                            attribute_type=attributes[
                                0
                            ],  # Use first attribute for context retrieval
                            abstract_id=abstract_id,
                            context_chunks=context_chunks_per_arm,
                            similarity_threshold=similarity_threshold,
                        )
                    )

                    # Extract attributes for this arm
                    arm_extraction_result = await self._extract_attributes_for_arm(
                        arm=arm,
                        attributes=attributes,
                        arm_context=arm_context,
                        abstract_id=abstract_id,
                        include_api_data=include_api_data,
                    )

                    arm_results[arm.arm_id] = arm_extraction_result
                    total_attributes_extracted += len(
                        arm_extraction_result.get("attributes", {})
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to extract attributes for arm {arm.arm_id}: {e}"
                    )
                    arm_results[arm.arm_id] = {
                        "arm_id": arm.arm_id,
                        "arm_name": arm.arm_name,
                        "attributes": {},
                        "errors": [f"Extraction failed: {str(e)}"],
                        "warnings": [],
                    }

            # Step 3: Calculate overall confidence and quality
            overall_confidence = self._calculate_overall_confidence(
                arm_results, separation_result
            )

            # Calculate processing time
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

            # Create result
            result = TreatmentArmExtractionResult(
                abstract_id=abstract_id,
                arm_results=arm_results,
                overall_confidence=overall_confidence,
                processing_time_ms=processing_time,
                total_attributes_extracted=total_attributes_extracted,
            )

            logger.info(
                f"Enhanced extraction completed: {total_attributes_extracted} attributes extracted"
            )
            return result

        except Exception as e:
            logger.error(f"Enhanced extraction failed: {e}")
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

            return TreatmentArmExtractionResult(
                abstract_id=abstract_id,
                arm_results={},
                overall_confidence=0.0,
                processing_time_ms=processing_time,
                errors=[f"Extraction failed: {str(e)}"],
            )

    async def extract_attributes_from_abstract_batch(
        self,
        abstract_text: str,
        abstract_id: str,
        attributes: list[AttributeType],
        context_chunks_per_arm: int = 5,
        similarity_threshold: float = 0.1,
        include_api_data: bool = True,
        file_path: Optional[str] = None,
    ) -> TreatmentArmExtractionResult:
        """Extract attributes from abstract using batch processing for efficiency.

        This method processes all attributes for all arms in batches, significantly
        reducing LLM API calls and improving processing speed.

        Args:
            abstract_text: Full abstract text
            abstract_id: Abstract identifier
            attributes: List of attributes to extract
            context_chunks_per_arm: Number of context chunks per arm
            similarity_threshold: Similarity threshold for RAG retrieval
            include_api_data: Whether to include Clinical Trials API data
            file_path: Optional file path for Conference/Year extraction

        Returns:
            Treatment arm extraction result
        """
        assert self.arm_aware_rag_provider is not None  # legacy path
        assert self.attribute_extractor is not None  # legacy path
        assert self.batch_extractor is not None  # legacy path
        start_time = datetime.now()

        try:
            logger.info(f"Starting batch extraction for abstract {abstract_id}")

            # Store file path for use in arm extraction
            self._current_file_path = file_path

            # Step 1: Separate treatment arms
            # For publications, extract Results section first and separate arms from it only
            is_pub = self._is_publication(abstract_text, file_path)
            text_for_arm_separation = abstract_text

            if is_pub:
                logger.info(
                    "Detected publication - extracting Results section for arm separation"
                )
                results_section = self._extract_results_section(abstract_text)
                if results_section:
                    text_for_arm_separation = results_section
                    logger.info(
                        f"Using Results section for arm separation ({len(results_section)} chars)"
                    )
                else:
                    logger.warning(
                        "Results section not found, using full publication text for arm separation"
                    )

            logger.info("Step 1: Separating treatment arms")
            separation_result = (
                await self.treatment_arm_separator.separate_treatment_arms(
                    text_for_arm_separation, abstract_id
                )
            )

            if not separation_result.treatment_arms:
                logger.warning(
                    f"No treatment arms identified for abstract {abstract_id}"
                )
                return TreatmentArmExtractionResult(
                    abstract_id=abstract_id,
                    arm_results={},
                    overall_confidence=0.0,
                    processing_time_ms=int(
                        (datetime.now() - start_time).total_seconds() * 1000
                    ),
                    errors=["No treatment arms identified"],
                )

            logger.info(
                f"Identified {len(separation_result.treatment_arms)} treatment arms"
            )

            # Step 2: NOTE - Context retrieval is now done PER ATTRIBUTE in Step 5
            # This enables our 3-tier RAG filtering (metadata, sub-chunking, keywords)
            logger.info(
                "Step 2: Deferring context retrieval to per-attribute processing"
            )

            # Step 3: Separate attributes by source and level
            from ..domain.extraction_models import AttributeConfigurationFactory

            file_path_attributes = []
            abstract_level_attributes = (
                []
            )  # Same value for all arms (ABSTRACT_NUMBER, NCT_NUMBER, COMMENTS)
            arm_level_attributes = []  # Different values per arm (most attributes)
            api_attributes = []

            abstract_level_attr_set = set(
                AttributeConfigurationFactory.get_abstract_level_attributes()
            )

            for attr_type in attributes:
                if self.file_path_extractor.can_extract_from_path(attr_type):
                    file_path_attributes.append(attr_type)
                else:
                    config = self.attribute_configs.get(attr_type)
                    if config and config.api_source:
                        api_attributes.append(attr_type)
                    elif attr_type in abstract_level_attr_set:
                        # Abstract-level: extract once, share across all arms
                        abstract_level_attributes.append(attr_type)
                    else:
                        # Arm-level: extract per arm
                        arm_level_attributes.append(attr_type)

            # Step 4: Extract file path attributes (once for all arms)
            file_path_results = {}
            if file_path_attributes:
                logger.info(
                    f"Extracting file path attributes: {[attr.value for attr in file_path_attributes]}"
                )
                file_path_results = self._extract_file_path_attributes_batch(
                    file_path_attributes, file_path
                )

            # Step 5: Extract abstract-level attributes (once, shared across all arms)
            abstract_level_results = {}
            if abstract_level_attributes:
                logger.info(
                    f"Extracting abstract-level attributes (shared across arms): {[attr.value for attr in abstract_level_attributes]}"
                )
                abstract_level_results = await self._extract_abstract_level_attributes(
                    attributes=abstract_level_attributes,
                    arms=separation_result.treatment_arms,
                    abstract_id=abstract_id,
                    similarity_threshold=similarity_threshold,
                    file_path=file_path,
                )

            # Step 6: Extract arm-level attributes using PER-ATTRIBUTE retrieval
            # This enables 3-tier RAG filtering (Tier 1: metadata, Tier 2: sub-chunking, Tier 3: keywords)
            arm_level_results = {}
            if arm_level_attributes:
                logger.info(
                    f"Extracting arm-level attributes in batch: {[attr.value for attr in arm_level_attributes]}"
                )
                arm_level_results = (
                    await self._extract_attributes_per_attribute_with_rag(
                        arms=separation_result.treatment_arms,
                        attributes=arm_level_attributes,
                        abstract_id=abstract_id,
                        context_chunks_per_arm=context_chunks_per_arm,
                        similarity_threshold=similarity_threshold,
                        file_path=file_path,
                    )
                )

            # Combine abstract-level and arm-level results
            abstract_results = {**abstract_level_results, **arm_level_results}

            # Step 7: Extract API attributes
            api_results = {}
            if api_attributes and include_api_data:
                logger.info(
                    f"Extracting API attributes: {[attr.value for attr in api_attributes]}"
                )
                # Get NCT number from abstract-level results if available (for publications,
                # NCT number is extracted from full text, not just Results section)
                nct_number_from_results = None
                if AttributeType.NCT_NUMBER in abstract_level_results:
                    # Get NCT number from any arm (they all have the same value for abstract-level attributes)
                    if separation_result.treatment_arms:
                        first_arm_id = separation_result.treatment_arms[0].arm_id
                        if (
                            first_arm_id
                            in abstract_level_results[AttributeType.NCT_NUMBER]
                        ):
                            nct_attr = abstract_level_results[AttributeType.NCT_NUMBER][
                                first_arm_id
                            ]
                            if hasattr(nct_attr, "value") and nct_attr.value:
                                nct_number_from_results = str(nct_attr.value).strip()
                                # Clean the NCT number
                                nct_number_from_results = self._clean_attribute_value(
                                    AttributeType.NCT_NUMBER, nct_number_from_results
                                )
                                logger.info(
                                    f"Found NCT number from abstract-level extraction: {nct_number_from_results}"
                                )

                # Fallback: If NCT number not in abstract-level results, try to extract it from full text
                # This is needed for publications where NCT might not be in the attributes list
                if not nct_number_from_results:
                    logger.debug(
                        "NCT number not found in abstract-level results, attempting direct extraction from full text"
                    )
                    try:
                        # Extract NCT number directly from full publication text
                        nct_context = (
                            await self.arm_aware_rag_provider.get_context_for_attribute(
                                document_id=abstract_id,
                                attribute_type=AttributeType.NCT_NUMBER,
                                context_chunks=3,
                                similarity_threshold=similarity_threshold,
                                metadata_filters={"filename": file_path}
                                if file_path
                                else None,
                            )
                        )
                        if nct_context:
                            nct_attr = await self.attribute_extractor.extract_attribute(
                                attribute_type=AttributeType.NCT_NUMBER,
                                context=nct_context,
                                document_id=abstract_id,
                            )
                            if hasattr(nct_attr, "value") and nct_attr.value:
                                nct_number_from_results = str(nct_attr.value).strip()
                                nct_number_from_results = self._clean_attribute_value(
                                    AttributeType.NCT_NUMBER, nct_number_from_results
                                )
                                logger.info(
                                    f"Found NCT number from direct extraction: {nct_number_from_results}"
                                )
                    except Exception as e:
                        logger.debug(f"Failed to extract NCT number directly: {e}")

                # Log the NCT number being passed to API extraction
                if nct_number_from_results:
                    logger.info(
                        f"Passing NCT number to API extraction: {nct_number_from_results}"
                    )
                else:
                    logger.warning(
                        "NCT number is None/empty when calling API extraction"
                    )

                api_results = await self._extract_api_attributes_batch(
                    separation_result.treatment_arms,
                    api_attributes,
                    abstract_id,
                    nct_number_from_results,
                )

            # Step 7b: Extract trial_name from API as fallback (even though it's not API-sourced)
            # This allows LLM extraction to take precedence, but API can fill in if LLM fails
            # API result must match 'Keynote-', 'Checkmate-', or 'Masterkey-' patterns
            if include_api_data and AttributeType.TRIAL_NAME in attributes:
                trial_name_found = False
                if AttributeType.TRIAL_NAME in abstract_results:
                    # Check if any arm has a valid trial name from LLM
                    for arm_attr_result in abstract_results[
                        AttributeType.TRIAL_NAME
                    ].values():
                        if hasattr(arm_attr_result, "value"):
                            value = str(arm_attr_result.value).strip()
                            if value and value not in [
                                "",
                                "Not found",
                                "Not available",
                                "No Name",
                            ]:
                                trial_name_found = True
                                break

                if not trial_name_found:
                    # LLM extraction failed or returned empty - try API as fallback
                    logger.info("Trial name not found via LLM, attempting API fallback")
                    trial_name_api_results = await self._extract_api_attributes_batch(
                        separation_result.treatment_arms,
                        [AttributeType.TRIAL_NAME],
                        abstract_id,
                    )
                    if trial_name_api_results:
                        # Use API trial name directly (briefTitle from API)
                        # No pattern validation needed - API provides the official trial title
                        for arm_id, api_result in trial_name_api_results[
                            AttributeType.TRIAL_NAME
                        ].items():
                            api_value = (
                                api_result.get("value", "")
                                if isinstance(api_result, dict)
                                else str(api_result)
                            )
                            api_value_str = str(api_value).strip()

                            # Only use if we have a valid value
                            if api_value_str and api_value_str not in [
                                "",
                                "Not found",
                                "None",
                            ]:
                                # Update the result with proper confidence for API data
                                trial_name_api_results[AttributeType.TRIAL_NAME][
                                    arm_id
                                ] = {
                                    "value": api_value_str,
                                    "source": "clinical_trials_api",
                                    "confidence": 0.9,  # High confidence for API data
                                }
                                logger.info(
                                    f"Using API trial name for arm {arm_id}: {api_value_str}"
                                )
                            else:
                                # If API returned empty/None, set to "No Name"
                                trial_name_api_results[AttributeType.TRIAL_NAME][
                                    arm_id
                                ] = {
                                    "value": "No Name",
                                    "source": "clinical_trials_api",
                                    "confidence": 0.0,
                                }
                                logger.warning(
                                    f"API trial name is empty for arm {arm_id}, returning 'No Name'"
                                )

                            api_results.update(trial_name_api_results)

            # Step 8: Combine results for each arm
            logger.info("Step 8: Combining results for each treatment arm")
            arm_results = {}
            total_attributes_extracted = 0

            for arm in separation_result.treatment_arms:
                arm_result: dict[str, Any] = {
                    "arm_id": arm.arm_id,
                    "arm_name": arm.arm_name,
                    "generic_name": arm.generic_name,
                    "brand_name": arm.brand_name,
                    "dose": arm.dose,
                    "dosing_schedule": arm.dosing_schedule,
                    "patient_count": arm.patient_count,
                    "line_of_treatment": arm.line_of_treatment.value
                    if hasattr(arm.line_of_treatment, "value")
                    else arm.line_of_treatment,
                    "arm_type": arm.arm_type.value
                    if hasattr(arm.arm_type, "value")
                    else arm.arm_type,
                    "combination_drugs": arm.combination_drugs,
                    "confidence_score": arm.confidence_score,
                    "source_text": arm.source_text,
                    "attributes": {},
                    "errors": [],
                    "warnings": [],
                }

                # Helper function to convert ExtractedAttribute to dict
                def attr_to_dict(attr: Any) -> dict[str, Any]:
                    """Convert ExtractedAttribute object to dictionary."""
                    if isinstance(attr, dict):
                        return attr
                    elif hasattr(attr, "value") and hasattr(attr, "confidence"):
                        # It's an ExtractedAttribute object
                        return {
                            "value": attr.value,
                            "confidence": attr.confidence,
                            "validation_status": (
                                attr.validation_status.value
                                if hasattr(attr.validation_status, "value")
                                else str(attr.validation_status)
                            ),
                            "source_chunks": (
                                attr.source_chunks
                                if hasattr(attr, "source_chunks")
                                else []
                            ),
                            "source": (
                                attr.source if hasattr(attr, "source") else "unknown"
                            ),
                        }
                    else:
                        # Fallback: try to convert to dict
                        return {"value": str(attr), "confidence": 0.0}

                # Combine all attribute sources for this arm
                for attr_type in attributes:
                    if attr_type in file_path_results:
                        arm_result["attributes"][attr_type.value] = attr_to_dict(
                            file_path_results[attr_type]
                        )
                    elif (
                        attr_type in abstract_results
                        and arm.arm_id in abstract_results[attr_type]
                    ):
                        arm_result["attributes"][attr_type.value] = attr_to_dict(
                            abstract_results[attr_type][arm.arm_id]
                        )
                    elif attr_type in abstract_results:
                        # Abstract-level attribute exists but missing for this arm
                        # This shouldn't happen, but if it does, use the first arm's value
                        # (abstract-level attributes are the same for all arms)
                        first_arm_id = list(abstract_results[attr_type].keys())[0]
                        logger.warning(
                            f"Abstract-level attribute {attr_type.value} missing for arm {arm.arm_id}, "
                            f"using value from arm {first_arm_id}"
                        )
                        arm_result["attributes"][attr_type.value] = attr_to_dict(
                            abstract_results[attr_type][first_arm_id]
                        )
                    elif (
                        attr_type in api_results
                        and arm.arm_id in api_results[attr_type]
                    ):
                        arm_result["attributes"][attr_type.value] = attr_to_dict(
                            api_results[attr_type][arm.arm_id]
                        )

                arm_results[arm.arm_id] = arm_result

                # Helper function to check if attribute has a valid (non-empty) value
                def has_valid_value(attr_data):
                    """Check if attribute data has a valid (non-empty) value."""
                    if isinstance(attr_data, dict):
                        value = attr_data.get("value")
                        if value is None:
                            return False
                        value_str = str(value).strip()
                        return value_str not in [
                            "",
                            "Not found",
                            "Not available",
                            "No Name",
                        ]
                    elif hasattr(attr_data, "value"):
                        value = attr_data.value
                        if value is None:
                            return False
                        value_str = str(value).strip()
                        return value_str not in [
                            "",
                            "Not found",
                            "Not available",
                            "No Name",
                        ]
                    return False

                # Calculate per-arm statistics - ONLY count attributes with valid values
                arm_attributes = arm_result["attributes"]

                # Count only successfully extracted attributes (non-empty values)
                arm_result["total_attributes"] = sum(
                    1
                    for attr_data in arm_attributes.values()
                    if has_valid_value(attr_data)
                )

                # Count API attributes with valid values
                arm_result["api_attributes"] = sum(
                    1
                    for attr_data in arm_attributes.values()
                    if has_valid_value(attr_data)
                    and (
                        (
                            isinstance(attr_data, dict)
                            and attr_data.get("source") == "clinical_trials_api"
                        )
                        or (
                            hasattr(attr_data, "source")
                            and attr_data.source == "clinical_trials_api"
                        )
                    )
                )

                # Count abstract attributes with valid values
                arm_result["abstract_attributes"] = sum(
                    1
                    for attr_data in arm_attributes.values()
                    if has_valid_value(attr_data)
                    and (
                        (
                            isinstance(attr_data, dict)
                            and attr_data.get("source")
                            in [
                                "abstract_extraction",
                                "abstract_llm_extraction",
                                "file_path",
                            ]
                        )
                        or (
                            hasattr(attr_data, "source")
                            and attr_data.source
                            in [
                                "abstract_extraction",
                                "abstract_llm_extraction",
                                "file_path",
                            ]
                        )
                    )
                )

                # Count only non-empty attributes for total_attributes_extracted
                non_empty_attributes = sum(
                    1
                    for attr_data in arm_attributes.values()
                    if has_valid_value(attr_data)
                )
                total_attributes_extracted += non_empty_attributes

            # Step 8: Calculate overall confidence and quality
            overall_confidence = self._calculate_overall_confidence(
                arm_results, separation_result
            )

            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

            logger.info(
                f"Batch extraction completed for abstract {abstract_id}: "
                f"{total_attributes_extracted} attributes across {len(arm_results)} arms "
                f"in {processing_time}ms"
            )

            return TreatmentArmExtractionResult(
                abstract_id=abstract_id,
                arm_results=arm_results,
                overall_confidence=overall_confidence,
                processing_time_ms=processing_time,
                total_attributes_extracted=total_attributes_extracted,
                errors=[],
                warnings=[],
            )

        except Exception as e:
            logger.error(f"Batch extraction failed: {e}")
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

            return TreatmentArmExtractionResult(
                abstract_id=abstract_id,
                arm_results={},
                overall_confidence=0.0,
                processing_time_ms=processing_time,
                errors=[f"Batch extraction failed: {str(e)}"],
            )

    async def _extract_attributes_for_arm(
        self,
        arm: TreatmentArm,
        attributes: list[AttributeType],
        arm_context: ArmSpecificContext,
        abstract_id: str,
        include_api_data: bool = True,
    ) -> dict[str, Any]:
        """Extract attributes for a specific treatment arm.

        Args:
            arm: Treatment arm to extract attributes for
            attributes: List of attributes to extract
            arm_context: RAG context for the arm
            abstract_id: Abstract identifier
            include_api_data: Whether to include API data

        Returns:
            Dictionary containing extracted attributes and metadata
        """
        assert self.arm_aware_rag_provider is not None  # legacy path
        assert self.attribute_extractor is not None  # legacy path
        extracted_attributes: dict[AttributeType, Any] = {}
        errors = []
        warnings = []

        # Get NCT number for API lookups
        nct_number = None
        if arm.arm_metadata and "nct_number" in arm.arm_metadata:
            nct_number = arm.arm_metadata["nct_number"]

        # Separate attributes by source
        file_path_attributes = []
        abstract_attributes = []
        api_attributes = []

        for attr_type in attributes:
            if self.file_path_extractor.can_extract_from_path(attr_type):
                file_path_attributes.append(attr_type)
            else:
                config = self.attribute_configs.get(attr_type)
                if config and config.api_source:
                    api_attributes.append(attr_type)
                else:
                    abstract_attributes.append(attr_type)

        # Extract file path-based attributes (Conference, Published Year)
        for attr_type in file_path_attributes:
            try:
                attr_name = (
                    attr_type.value if hasattr(attr_type, "value") else str(attr_type)
                )
                logger.debug(f"Extracting file path attribute: {attr_name}")

                # Get file path from the service call context
                # For now, we'll pass it through the arm context or use a default
                file_path_value = None
                if hasattr(self, "_current_file_path") and self._current_file_path:
                    file_path_value = (
                        self.file_path_extractor.extract_attribute_from_path(
                            attr_type, self._current_file_path
                        )
                    )

                if file_path_value is not None:
                    extracted_attributes[attr_type] = {
                        "value": file_path_value,
                        "source": "file_path",
                        "confidence": 1.0,  # High confidence for file path extraction
                    }
                else:
                    warnings.append(f"Could not extract {attr_name} from file path")

            except Exception as e:
                attr_name = (
                    attr_type.value if hasattr(attr_type, "value") else str(attr_type)
                )
                logger.error(f"Failed to extract {attr_name} from file path: {e}")
                errors.append(f"Failed to extract {attr_name} from file path: {str(e)}")

        # Extract abstract-level attributes using RAG + LLM
        for attr_type in abstract_attributes:
            try:
                attr_name = (
                    attr_type.value if hasattr(attr_type, "value") else str(attr_type)
                )
                logger.debug(f"Extracting abstract attribute: {attr_name}")
                logger.debug(f"attr_type: {attr_type} (type: {type(attr_type)})")

                # Get context for this specific attribute
                # Pass file_path as metadata_filters for publication detection (needed for proper chunk type filtering)
                metadata_filters = None
                if hasattr(self, "_current_file_path") and self._current_file_path:
                    metadata_filters = {"filename": self._current_file_path}

                attr_context = (
                    await self.arm_aware_rag_provider.get_context_for_arm_attribute(
                        arm=arm,
                        attribute_type=attr_type,
                        abstract_id=abstract_id,
                        context_chunks=5,
                        similarity_threshold=0.1,
                        metadata_filters=metadata_filters,
                    )
                )

                # Get extraction prompt
                context_texts = [
                    chunk["content"] for chunk in attr_context.context_chunks
                ]

                # Debug: Check attr_type before calling get_extraction_prompt
                logger.debug(
                    f"About to call get_extraction_prompt with attr_type: {attr_type} (type: {type(attr_type)})"
                )

                # Extract attribute using LLM
                arm_info = {
                    "arm_id": arm.arm_id,
                    "arm_name": arm.arm_name,
                    "generic_name": arm.generic_name,
                    "dose": arm.dose,
                }
                extracted_value = await self.attribute_extractor.extract_attribute(
                    attribute_type=attr_type,
                    context=context_texts,
                    document_id=abstract_id,
                    arm_info=arm_info,
                )

                if extracted_value is not None:
                    # Extract clean value from Pydantic object
                    clean_value = (
                        extracted_value.value
                        if hasattr(extracted_value, "value")
                        else str(extracted_value)
                    )

                    # Post-process cleanup for specific attribute types
                    clean_value = self._clean_attribute_value(attr_type, clean_value)

                    extracted_attributes[attr_type] = {
                        "value": clean_value,
                        "source": "abstract_extraction",
                        "confidence": getattr(extracted_value, "confidence", 0.8),
                        "context_chunks": len(attr_context.context_chunks),
                    }
                else:
                    attr_name = (
                        attr_type.value
                        if hasattr(attr_type, "value")
                        else str(attr_type)
                    )
                    warnings.append(f"Could not extract {attr_name} from abstract")

            except Exception as e:
                # Debug: Check what attr_type is at this point
                logger.debug(
                    f"Exception occurred for attr_type: {attr_type} (type: {type(attr_type)})"
                )
                logger.debug(f"Exception: {e}")
                logger.debug(f"Exception type: {type(e)}")

                attr_name = (
                    attr_type.value if hasattr(attr_type, "value") else str(attr_type)
                )
                logger.error(f"Failed to extract {attr_name}: {e}")
                errors.append(f"Failed to extract {attr_name}: {str(e)}")

        # Extract API-sourced attributes
        if include_api_data and self.clinical_trials_api_service and nct_number:
            try:
                logger.debug(f"Fetching API data for NCT: {nct_number}")
                # Prepare arm info for API service (only include fields that exist in TreatmentArm model)
                arm_info = {
                    "arm_id": arm.arm_id,
                    "arm_name": arm.arm_name,
                    "generic_name": arm.generic_name,
                    "brand_name": arm.brand_name,
                    "dose": arm.dose,
                    "dosing_schedule": arm.dosing_schedule,
                }

                api_data = self.clinical_trials_api_service.get_multiple_attributes(
                    nct_number, api_attributes, arm_info
                )

                for attr_type, value in api_data.items():
                    if value is not None:
                        # Clean the value before storing
                        cleaned_value = self._clean_attribute_value(attr_type, value)
                        extracted_attributes[attr_type] = {
                            "value": cleaned_value,
                            "source": "clinical_trials_api",
                            "confidence": 0.9,  # High confidence for API data
                            "nct_number": nct_number,
                        }
                    else:
                        attr_name = (
                            attr_type.value
                            if hasattr(attr_type, "value")
                            else str(attr_type)
                        )
                        warnings.append(f"API data not available for {attr_name}")

            except Exception as e:
                logger.error(f"Failed to fetch API data: {e}")
                errors.append(f"Failed to fetch API data: {str(e)}")

        # Handle special cases and optimizations
        extracted_attributes = self._handle_special_cases(
            extracted_attributes, arm, nct_number
        )

        return {
            "arm_id": arm.arm_id,
            "arm_name": arm.arm_name,
            "attributes": extracted_attributes,
            "errors": errors,
            "warnings": warnings,
            "total_attributes": len(extracted_attributes),
            "api_attributes": len(
                [
                    a
                    for a in extracted_attributes.values()
                    if a.get("source") == "clinical_trials_api"
                ]
            ),
            "abstract_attributes": len(
                [
                    a
                    for a in extracted_attributes.values()
                    if a.get("source") == "abstract_extraction"
                ]
            ),
        }

    def _clean_attribute_value(self, attribute_type: AttributeType, value: Any) -> Any:
        """Clean attribute value based on its type.

        Args:
            attribute_type: Type of attribute
            value: Raw value to clean

        Returns:
            Cleaned value
        """
        if value is None or value == "Not found" or value == "":
            return value

        # Special handling for ABSTRACT_NUMBER - should be string, not float
        if attribute_type == AttributeType.ABSTRACT_NUMBER:
            if isinstance(value, (int, float)):
                return str(int(float(value)))
            # Extract numeric part from string if present
            import re

            numeric_match = re.search(r"\d+", str(value))
            if numeric_match:
                return numeric_match.group(0)
            return str(value).strip()

        # Special handling for NCT_NUMBER - supports NCT, EudraCT, and other identifiers
        if attribute_type == AttributeType.NCT_NUMBER:
            import re

            value_str = str(value).strip()

            # Trial identifier patterns (priority order)
            trial_id_patterns = [
                (r"NCT\d{8}", "NCT"),  # NCT number (highest priority)
                (r"EudraCT[:\s]*(\d{4}-\d{6}-\d{2,3})", "EudraCT"),  # EudraCT format
                (r"EudraCT[:\s]*(\d+)", "EudraCT"),  # EudraCT simple format
            ]

            # Try each pattern in priority order
            for pattern, prefix in trial_id_patterns:
                match = re.search(pattern, value_str, re.IGNORECASE)
                if match:
                    if prefix == "NCT":
                        return match.group(0)  # Full match for NCT
                    elif prefix == "EudraCT":
                        # Format EudraCT properly
                        eudract_value = (
                            match.group(1) if match.lastindex else match.group(0)
                        )
                        # Clean up the value - remove non-digit/non-dash characters
                        eudract_value = re.sub(r"[^\d-]", "", eudract_value)
                        return f"EudraCT: {eudract_value}"

            # Fallback: If it's already in correct format, use it
            if re.match(r"^NCT\d{8}$", value_str):
                return value_str
            # Try to extract NCT number from the value
            nct_match = re.search(r"NCT\d{8}", value_str)
            if nct_match:
                return nct_match.group(0)
            # If it's just digits (like 3086174.0), convert to NCT format
            # Handle decimal numbers by extracting integer part before decimal
            if "." in value_str:
                # Extract integer part before decimal (e.g., "3086174.0" -> "3086174")
                integer_part = value_str.split(".")[0]
                digits_match = re.search(r"\d+", integer_part)
            else:
                digits_match = re.search(r"\d+", value_str)

            if digits_match:
                digits = digits_match.group(0)
                # Pad to 8 digits if needed
                if len(digits) == 7:
                    digits = "0" + digits
                if len(digits) == 8:
                    return f"NCT{digits}"
            return value_str

        return value

    def _handle_special_cases(
        self,
        extracted_attributes: dict[AttributeType, Any],
        arm: TreatmentArm,
        nct_number: Optional[str],
    ) -> dict[AttributeType, Any]:
        """Handle special cases and optimizations for attribute extraction.

        Args:
            extracted_attributes: Currently extracted attributes
            arm: Treatment arm
            nct_number: NCT number if available

        Returns:
            Updated extracted attributes
        """
        # Direct propagation of NCT number from arm separation
        if nct_number and AttributeType.NCT_NUMBER not in extracted_attributes:
            # Clean the NCT number value
            cleaned_nct = self._clean_attribute_value(
                AttributeType.NCT_NUMBER, nct_number
            )
            extracted_attributes[AttributeType.NCT_NUMBER] = {
                "value": cleaned_nct,
                "source": "arm_separation",
                "confidence": 1.0,
            }

        # Direct propagation of generic name from arm separation
        if arm.arm_metadata and "generic_name" in arm.arm_metadata:
            generic_name = arm.arm_metadata["generic_name"]
            if generic_name and AttributeType.GENERIC_NAME not in extracted_attributes:
                extracted_attributes[AttributeType.GENERIC_NAME] = {
                    "value": generic_name,
                    "source": "arm_separation",
                    "confidence": 1.0,
                }

        return extracted_attributes

    def _calculate_overall_confidence(
        self,
        arm_results: dict[str, Any],
        separation_result: TreatmentArmSeparationResult,
    ) -> float:
        """Calculate overall confidence score for the extraction.

        Args:
            arm_results: Results for each treatment arm
            separation_result: Treatment arm separation result

        Returns:
            Overall confidence score (0.0-1.0)
        """
        if not arm_results:
            return 0.0

        total_confidence = 0.0
        total_attributes = 0

        for arm_result in arm_results.values():
            attributes = arm_result.get("attributes", {})
            for attr_data in attributes.values():
                if isinstance(attr_data, dict) and "confidence" in attr_data:
                    total_confidence += attr_data["confidence"]
                    total_attributes += 1

        if total_attributes == 0:
            return 0.0

        return total_confidence / total_attributes

    def get_extraction_summary(
        self, result: TreatmentArmExtractionResult
    ) -> dict[str, Any]:
        """Get a summary of the extraction results.

        Args:
            result: Treatment arm extraction result

        Returns:
            Summary dictionary
        """
        total_arms = len(result.arm_results)
        total_attributes = result.total_attributes_extracted
        overall_confidence = result.overall_confidence

        # Count attributes by source
        api_attributes = 0
        abstract_attributes = 0
        arm_separation_attributes = 0

        for arm_result in result.arm_results.values():
            attributes = arm_result.get("attributes", {})
            for attr_data in attributes.values():
                if hasattr(attr_data, "source"):
                    source = attr_data.source
                elif isinstance(attr_data, dict):
                    source = attr_data.get("source", "unknown")
                else:
                    source = "unknown"

                if source == "clinical_trials_api":
                    api_attributes += 1
                elif source in ["abstract_extraction", "abstract_llm_extraction"]:
                    abstract_attributes += 1
                elif source == "arm_separation":
                    arm_separation_attributes += 1

        return {
            "abstract_id": result.abstract_id,
            "total_arms": total_arms,
            "total_attributes": total_attributes,
            "overall_confidence": overall_confidence,
            "processing_time_ms": result.processing_time_ms,
            "attribute_sources": {
                "api": api_attributes,
                "abstract": abstract_attributes,
                "arm_separation": arm_separation_attributes,
            },
            "errors": result.errors,
            "warnings": result.warnings,
        }

    def get_cost_summary(self):
        """Get current cost summary if cost tracking is enabled.

        Returns:
            CostSummary or None if cost tracking is disabled
        """
        if self.cost_tracking_enabled and self.cost_calculator:
            return self.cost_calculator.get_summary()
        return None

    def print_cost_summary(self):
        """Print formatted cost summary if cost tracking is enabled."""
        if self.cost_tracking_enabled and self.cost_calculator:
            self.cost_calculator.print_summary()
        else:
            logger.info("Cost tracking is not enabled")

    def save_cost_report(self, filepath: str):
        """Save detailed cost report if cost tracking is enabled.

        Args:
            filepath: Path to save the report
        """
        if self.cost_tracking_enabled and self.cost_calculator:
            self.cost_calculator.save_detailed_report(filepath)
        else:
            logger.info("Cost tracking is not enabled")

    def reset_cost_tracking(self):
        """Reset cost tracking if enabled."""
        if self.cost_tracking_enabled and self.cost_calculator:
            self.cost_calculator.reset()
            logger.info("Cost tracking reset")

    async def _extract_abstract_level_attributes(
        self,
        attributes: list[AttributeType],
        arms: list[TreatmentArm],
        abstract_id: str,
        similarity_threshold: float,
        file_path: Optional[str] = None,
    ) -> dict[AttributeType, dict[str, ExtractedAttribute]]:
        """Extract abstract-level attributes (same value for all arms).

        Abstract-level attributes like ABSTRACT_NUMBER, NCT_NUMBER, COMMENTS
        are the same for all treatment arms in an abstract. This method extracts
        them once and shares the value across all arms.

        Args:
            attributes: List of abstract-level attributes to extract
            arms: List of treatment arms (to distribute results to)
            abstract_id: Abstract identifier
            similarity_threshold: Similarity threshold for RAG retrieval

        Returns:
            Dictionary mapping attribute types to arm results (same value for all arms)
        """
        assert self.arm_aware_rag_provider is not None  # legacy path
        assert self.attribute_extractor is not None  # legacy path
        logger.info(
            f"Extracting {len(attributes)} abstract-level attributes (shared across all arms)"
        )

        results: dict[AttributeType, dict[str, ExtractedAttribute]] = {}

        for attribute in attributes:
            try:
                # Get attribute-specific context with 3-tier filtering
                # Pass file_path as metadata_filters for publication detection (needed for NCT_NUMBER)
                metadata_filters = None
                if file_path:
                    metadata_filters = {"filename": file_path}

                context_texts = (
                    await self.arm_aware_rag_provider.get_context_for_attribute(
                        document_id=abstract_id,
                        attribute_type=attribute,
                        context_chunks=3,
                        similarity_threshold=similarity_threshold,
                        metadata_filters=metadata_filters,
                    )
                )

                # Special handling for COMMENTS: if no chunks found, return empty string immediately
                # (COMMENTS uses fixed section 'full_text_reference' which may not exist)
                if attribute == AttributeType.COMMENTS and not context_texts:
                    logger.info(
                        "No chunks found for COMMENTS (full_text_reference section doesn't exist) - returning empty string"
                    )
                    arm_results: dict[str, ExtractedAttribute] = {}
                    for arm in arms:
                        arm_results[arm.arm_id] = ExtractedAttribute(
                            attribute_type=attribute,
                            value="",
                            confidence=1.0,  # High confidence: we know the section doesn't exist
                            source="abstract_llm_extraction",
                        )
                    results[attribute] = arm_results
                    continue

                # 💰 COST OPTIMIZATION: Skip LLM call if no chunks retrieved
                # If 3-tier filtering removed all chunks, return "Not found" immediately
                if not context_texts:
                    logger.debug(
                        f"No chunks retrieved for abstract-level attribute {attribute.value} after 3-tier filtering - skipping LLM call"
                    )
                    arm_results_not_found: dict[str, ExtractedAttribute] = {}
                    for arm in arms:
                        arm_results_not_found[arm.arm_id] = ExtractedAttribute(
                            attribute_type=attribute,
                            value="Not found",
                            confidence=0.0,
                            source="abstract_llm_extraction",
                        )
                    results[attribute] = arm_results_not_found
                    continue

                # Extract attribute once (no arm-specific extraction needed)
                extracted_value = await self.attribute_extractor.extract_attribute(
                    attribute_type=attribute,
                    context=context_texts,
                    document_id=abstract_id,
                    arm_info=None,  # No arm info for abstract-level attributes
                )

                # Share the same value across all arms
                arm_results = {}
                for arm in arms:
                    arm_results[arm.arm_id] = extracted_value

                results[attribute] = arm_results
                logger.debug(
                    f"Extracted {attribute.value} for {len(arms)} arms: {extracted_value.value if hasattr(extracted_value, 'value') else str(extracted_value)}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to extract abstract-level attribute {attribute.value}: {e}",
                    exc_info=True,
                )
                # Create "Not found" results for all arms
                arm_results = {}
                for arm in arms:
                    arm_results[arm.arm_id] = ExtractedAttribute(
                        attribute_type=attribute,
                        value="Not found",
                        confidence=0.0,
                        source="abstract_llm_extraction",
                    )
                results[attribute] = arm_results
                continue

        return results

    async def _extract_attributes_per_attribute_with_rag(
        self,
        arms: list[TreatmentArm],
        attributes: list[AttributeType],
        abstract_id: str,
        context_chunks_per_arm: int,
        similarity_threshold: float,
        file_path: Optional[str] = None,
    ) -> dict[AttributeType, dict[str, ExtractedAttribute]]:
        """Extract attributes with per-attribute RAG retrieval (3-tier filtering).

        This method enables our 3-tier RAG optimization:
        - Tier 1: Metadata filtering (e.g., only 'results' sections for numeric attributes)
        - Tier 2: Sub-chunking (breaking large sections into semantic units)
        - Tier 3: Keyword filtering (ensuring relevant terms are present)

        🎯 EFFICIENCY: Uses BatchAttributeExtractor to make 1 LLM call per attribute
        (not 1 per arm), extracting values for all arms simultaneously.

        Args:
            arms: List of treatment arms
            attributes: List of attributes to extract
            abstract_id: Abstract identifier
            context_chunks_per_arm: Number of context chunks per arm
            similarity_threshold: Similarity threshold for RAG retrieval

        Returns:
            Dictionary mapping attribute types to arm results
        """
        assert self.arm_aware_rag_provider is not None  # legacy path
        assert self.batch_extractor is not None  # legacy path
        logger.info(
            f"Starting per-attribute extraction with 3-tier RAG for {len(attributes)} attributes across {len(arms)} arms"
        )

        is_publication = bool(file_path and "Publications" in file_path)
        extraction_source = (
            "publication_llm_extraction"
            if is_publication
            else "abstract_llm_extraction"
        )
        metadata_filters = {"filename": file_path} if file_path else None

        sem = asyncio.Semaphore(self.max_concurrent_attributes)

        rag_provider = self.arm_aware_rag_provider
        batch_extractor = self.batch_extractor

        async def _process_attribute(
            attribute: AttributeType,
        ) -> tuple[AttributeType, dict[str, ExtractedAttribute]]:
            async with sem:
                not_found = {
                    arm.arm_id: ExtractedAttribute(
                        attribute_type=attribute,
                        value="Not found",
                        confidence=0.0,
                        source=extraction_source,
                    )
                    for arm in arms
                }
                try:
                    context_texts = await rag_provider.get_context_for_attribute(
                        document_id=abstract_id,
                        attribute_type=attribute,
                        context_chunks=3,
                        similarity_threshold=similarity_threshold,
                        metadata_filters=metadata_filters,
                    )
                    if not context_texts:
                        logger.debug(
                            f"No chunks retrieved for {attribute.value} after 3-tier filtering - skipping LLM call"
                        )
                        return (attribute, not_found)
                    single_attr_results = (
                        await batch_extractor._extract_single_attribute_for_all_arms(
                            arms=arms,
                            attribute=attribute,
                            context=context_texts,
                            document_id=abstract_id,
                            source=extraction_source,
                        )
                    )
                    return (attribute, single_attr_results)
                except Exception as e:
                    logger.error(f"Failed to process attribute {attribute.value}: {e}")
                    return (attribute, not_found)

        tasks = [_process_attribute(attr) for attr in attributes]
        attribute_pairs = await asyncio.gather(*tasks)
        results = dict(attribute_pairs)

        logger.info(
            f"Per-attribute extraction completed: {len(results)} attribute types processed"
        )
        return results

    def _extract_file_path_attributes_batch(
        self,
        attributes: list[AttributeType],
        file_path: Optional[str],
    ) -> dict[AttributeType, dict[str, Any]]:
        """Extract file path attributes in batch.

        Args:
            attributes: List of file path attributes
            file_path: File path to extract from

        Returns:
            Dictionary mapping attribute types to their values
        """
        results = {}

        if not file_path:
            logger.warning("No file path provided for file path attribute extraction")
            for attr_type in attributes:
                results[attr_type] = {
                    "value": "Not found",
                    "source": "file_path",
                    "confidence": 0.0,
                }
            return results

        for attr_type in attributes:
            try:
                value = self.file_path_extractor.extract_attribute_from_path(
                    attr_type, file_path
                )
                results[attr_type] = {
                    "value": value if value is not None else "Not found",
                    "source": "file_path",
                    "confidence": 1.0 if value is not None else 0.0,
                }
            except Exception as e:
                logger.error(f"Failed to extract {attr_type.value} from file path: {e}")
                results[attr_type] = {
                    "value": "Not found",
                    "source": "file_path",
                    "confidence": 0.0,
                }

        return results

    async def _extract_api_attributes_batch(
        self,
        arms: list[TreatmentArm],
        attributes: list[AttributeType],
        abstract_id: str,
        nct_number_override: Optional[str] = None,
    ) -> dict[AttributeType, dict[str, Any]]:
        """Extract API attributes in batch.

        Args:
            arms: List of treatment arms
            attributes: List of API attributes
            abstract_id: Abstract identifier
            nct_number_override: Optional NCT number from abstract-level extraction
                               (used for publications where NCT is not in Results section)

        Returns:
            Dictionary mapping attribute types to arm results
        """
        results: dict[AttributeType, dict[str, Any]] = {}

        if not self.clinical_trials_api_service:
            logger.warning("Clinical Trials API service not available")
            for attr_type in attributes:
                results[attr_type] = {}
                for arm in arms:
                    results[attr_type][arm.arm_id] = {
                        "value": "Not found",
                        "source": "clinical_trials_api",
                        "confidence": 0.0,
                    }
            return results

        # Get NCT number - prioritize override (from abstract-level extraction) over arm metadata
        # For publications, NCT number is extracted from full text, not just Results section
        nct_number = nct_number_override
        if nct_number:
            logger.info(
                f"Using NCT number from override (abstract-level/direct extraction): {nct_number}"
            )
        elif arms and arms[0].arm_metadata and "nct_number" in arms[0].arm_metadata:
            nct_number = arms[0].arm_metadata["nct_number"]
            if nct_number:
                logger.debug(f"Using NCT number from arm metadata: {nct_number}")

        if not nct_number:
            logger.warning(
                f"No NCT number found for API attribute extraction (override={nct_number_override}, checked both abstract-level results and arm metadata)"
            )
            for attr_type in attributes:
                results[attr_type] = {}
                for arm in arms:
                    results[attr_type][arm.arm_id] = {
                        "value": "Not found",
                        "source": "clinical_trials_api",
                        "confidence": 0.0,
                    }
            return results

        # Extract API data for each arm
        for arm in arms:
            try:
                arm_info = {
                    "arm_id": arm.arm_id,
                    "arm_name": arm.arm_name,
                    "generic_name": arm.generic_name,
                    "brand_name": arm.brand_name,
                    "dose": arm.dose,
                    "dosing_schedule": arm.dosing_schedule,
                }

                api_data = self.clinical_trials_api_service.get_multiple_attributes(
                    nct_number, attributes, arm_info
                )

                # Store results for this arm
                for attr_type in attributes:
                    if attr_type not in results:
                        results[attr_type] = {}

                    value = api_data.get(attr_type)
                    results[attr_type][arm.arm_id] = {
                        "value": value if value is not None else "Not found",
                        "source": "clinical_trials_api",
                        "confidence": 0.9 if value is not None else 0.0,
                    }

            except Exception as e:
                logger.error(f"Failed to extract API data for arm {arm.arm_id}: {e}")
                for attr_type in attributes:
                    if attr_type not in results:
                        results[attr_type] = {}
                    results[attr_type][arm.arm_id] = {
                        "value": "Not found",
                        "source": "clinical_trials_api",
                        "confidence": 0.0,
                    }

        return results
