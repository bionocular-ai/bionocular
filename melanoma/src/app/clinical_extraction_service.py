"""Clinical data extraction service for oncology abstracts.

This service provides sophisticated clinical data extraction capabilities using
LangChain's structured output features and custom clinical prompts for
oncology abstract processing.
"""

import logging
from typing import Any, Optional

from langchain_core.language_models import BaseLLM

from ..domain.models import ChunkWithEmbedding
from ..infrastructure.langchain import (
    ClinicalTrialData,
    LangChainClinicalService,
)

logger = logging.getLogger(__name__)


class ClinicalDataProcessor:
    """Processes clinical data extraction results.

    This class encapsulates all clinical data processing logic including
    validation, enrichment, and quality assessment. It's separated to
    maintain single responsibility and make the processing logic testable.
    """

    def __init__(self):
        """Initialize the clinical data processor."""
        self.quality_thresholds = {
            "high_confidence": 0.8,
            "medium_confidence": 0.5,
            "low_confidence": 0.3,
        }

    def validate_trial_data(self, trial_data: ClinicalTrialData) -> dict[str, Any]:
        """Validate clinical trial data quality.

        Args:
            trial_data: Clinical trial data to validate

        Returns:
            Validation results dictionary
        """
        validation_results: dict[str, Any] = {
            "is_valid": True,
            "quality_score": 0.0,
            "missing_fields": [],
            "quality_issues": [],
            "recommendations": [],
        }

        # Check for essential fields
        essential_fields = [
            "trial_id",
            "title",
            "study_design",
            "treatment_arms",
            "primary_endpoint",
            "efficacy_results",
        ]

        missing_fields = []
        for field in essential_fields:
            value = getattr(trial_data, field)
            if not value or (isinstance(value, str) and not value.strip()):
                missing_fields.append(field)

        validation_results["missing_fields"] = missing_fields

        # Calculate quality score
        total_fields = len(essential_fields)
        present_fields = total_fields - len(missing_fields)
        quality_score = present_fields / total_fields

        validation_results["quality_score"] = quality_score

        # Determine quality level
        if quality_score >= self.quality_thresholds["high_confidence"]:
            quality_level = "high"
        elif quality_score >= self.quality_thresholds["medium_confidence"]:
            quality_level = "medium"
        else:
            quality_level = "low"

        validation_results["quality_level"] = quality_level

        # Add quality issues
        if missing_fields:
            validation_results["quality_issues"].append(
                f"Missing essential fields: {', '.join(missing_fields)}"
            )

        if trial_data.confidence_score and trial_data.confidence_score < 0.5:
            validation_results["quality_issues"].append(
                "Low confidence score in extraction"
            )

        # Add recommendations
        if missing_fields:
            validation_results["recommendations"].append(
                "Consider manual review for missing essential fields"
            )

        if quality_score < 0.7:
            validation_results["recommendations"].append(
                "Consider re-extraction with different prompts"
            )

        return validation_results

    def enrich_trial_data(self, trial_data: ClinicalTrialData) -> ClinicalTrialData:
        """Enrich clinical trial data with additional information.

        Args:
            trial_data: Clinical trial data to enrich

        Returns:
            Enriched clinical trial data
        """
        # Add quality indicators
        validation_results = self.validate_trial_data(trial_data)
        trial_data.extraction_notes = f"Quality: {validation_results['quality_level']}, Score: {validation_results['quality_score']:.2f}"

        # Note: ClinicalTrialData doesn't have extraction_metadata attribute
        # Store validation info in extraction_notes instead
        if trial_data.extraction_notes:
            trial_data.extraction_notes += f" | Validation: {validation_results['quality_level']}"
        else:
            trial_data.extraction_notes = f"Validation: {validation_results['quality_level']}"

        return trial_data

    def format_trial_data_for_display(
        self, trial_data: ClinicalTrialData
    ) -> dict[str, Any]:
        """Format trial data for display purposes.

        Args:
            trial_data: Clinical trial data to format

        Returns:
            Formatted data dictionary
        """
        return {
            "trial_id": trial_data.trial_id or "Not available",
            "title": trial_data.title or "Not available",
            "study_design": trial_data.study_design or "Not available",
            "phase": trial_data.phase or "Not available",
            "treatment_arms": trial_data.treatment_arms or [],
            "primary_endpoint": trial_data.primary_endpoint or "Not available",
            "efficacy_results": trial_data.efficacy_results or "Not available",
            "safety_results": trial_data.safety_results or "Not available",
            "sponsor": trial_data.sponsor or "Not available",
            "conference": trial_data.conference or "Not available",
            "year": trial_data.year or "Not available",
            "confidence_score": trial_data.confidence_score or 0.0,
            "quality_indicators": {
                "has_trial_id": bool(trial_data.trial_id),
                "has_title": bool(trial_data.title),
                "has_endpoints": bool(trial_data.primary_endpoint),
                "has_results": bool(trial_data.efficacy_results),
            },
        }


class ClinicalExtractionService:
    """Clinical data extraction service for oncology abstracts.

    This service provides sophisticated clinical data extraction capabilities
    using LangChain's structured output features and custom clinical prompts
    for oncology abstract processing.
    """

    def __init__(
        self,
        llm: BaseLLM,
        prompts_path: Optional[str] = None,
    ):
        """Initialize the clinical extraction service.

        Args:
            llm: LLM instance for data extraction
            prompts_path: Path to custom prompts file
        """
        self.llm = llm
        self.prompts_path = prompts_path

        # Initialize LangChain clinical service
        self.langchain_clinical_service = LangChainClinicalService(
            llm=llm, prompts_path=prompts_path
        )

        # Initialize data processor
        self.data_processor = ClinicalDataProcessor()

        logger.info("Clinical extraction service initialized")

    async def extract_clinical_data(
        self,
        chunks: list[ChunkWithEmbedding],
        enrich_data: bool = True,
        validate_data: bool = True,
    ) -> list[ClinicalTrialData]:
        """Extract clinical data from chunks.

        Args:
            chunks: List of chunks to extract data from
            enrich_data: Whether to enrich the extracted data
            validate_data: Whether to validate the extracted data

        Returns:
            List of extracted clinical trial data

        Raises:
            RuntimeError: If extraction fails
        """
        try:
            logger.info(f"Starting clinical data extraction from {len(chunks)} chunks")

            # Extract trial data using LangChain service
            trial_data_list = (
                await self.langchain_clinical_service.extract_clinical_data(chunks)
            )

            # Process each trial data
            processed_trial_data = []
            for trial_data in trial_data_list:
                # Validate data if requested
                if validate_data:
                    validation_results = self.data_processor.validate_trial_data(
                        trial_data
                    )
                    logger.info(
                        f"Trial data validation: {validation_results['quality_level']} quality"
                    )

                # Enrich data if requested
                if enrich_data:
                    trial_data = self.data_processor.enrich_trial_data(trial_data)

                processed_trial_data.append(trial_data)

            logger.info(
                f"Successfully extracted clinical data for {len(processed_trial_data)} trials"
            )
            return processed_trial_data

        except Exception as e:
            logger.error(f"Clinical data extraction failed: {e}")
            raise RuntimeError(f"Clinical data extraction failed: {e}") from e

    async def extract_trial_data_from_text(
        self,
        text: str,
        enrich_data: bool = True,
        validate_data: bool = True,
    ) -> ClinicalTrialData:
        """Extract clinical trial data from text.

        Args:
            text: Text to extract data from
            enrich_data: Whether to enrich the extracted data
            validate_data: Whether to validate the extracted data

        Returns:
            Extracted clinical trial data
        """
        try:
            # Create a mock chunk for the text
            from uuid import uuid4

            from ..domain.models import ChunkType

            mock_chunk = ChunkWithEmbedding(
                id=uuid4(),
                document_id=str(uuid4()),
                content=text,
                chunk_type=ChunkType.FULL_ABSTRACT,
                metadata={},
                sequence_number=0,
                token_count=len(text.split()),
            )

            # Extract data
            trial_data_list = await self.extract_clinical_data(
                [mock_chunk], enrich_data, validate_data
            )

            if trial_data_list:
                return trial_data_list[0]
            # Return empty ClinicalTrialData with all Optional fields as None
            return ClinicalTrialData.model_construct()

        except Exception as e:
            logger.error(f"Trial data extraction from text failed: {e}")
            raise RuntimeError(f"Trial data extraction from text failed: {e}") from e

    def get_extraction_statistics(
        self, trial_data_list: list[ClinicalTrialData]
    ) -> dict[str, Any]:
        """Get statistics about the extraction results.

        Args:
            trial_data_list: List of extracted trial data

        Returns:
            Dictionary containing extraction statistics
        """
        if not trial_data_list:
            return {"total_trials": 0}

        # Calculate quality metrics
        quality_scores = [trial.confidence_score or 0.0 for trial in trial_data_list]
        average_quality = sum(quality_scores) / len(quality_scores)

        # Count trials by quality level
        quality_levels = {"high": 0, "medium": 0, "low": 0}
        for trial in trial_data_list:
            score = trial.confidence_score or 0.0
            if score >= 0.8:
                quality_levels["high"] += 1
            elif score >= 0.5:
                quality_levels["medium"] += 1
            else:
                quality_levels["low"] += 1

        # Count trials with essential fields
        essential_fields = ["trial_id", "title", "primary_endpoint", "efficacy_results"]
        field_completeness = {}
        for field in essential_fields:
            count = sum(1 for trial in trial_data_list if getattr(trial, field))
            field_completeness[field] = count / len(trial_data_list)

        return {
            "total_trials": len(trial_data_list),
            "average_quality_score": average_quality,
            "quality_distribution": quality_levels,
            "field_completeness": field_completeness,
            "high_quality_trials": quality_levels["high"],
            "medium_quality_trials": quality_levels["medium"],
            "low_quality_trials": quality_levels["low"],
        }

    def format_trial_data_for_export(
        self, trial_data_list: list[ClinicalTrialData], format_type: str = "json"
    ) -> str:
        """Format trial data for export.

        Args:
            trial_data_list: List of trial data to format
            format_type: Export format (json, csv, etc.)

        Returns:
            Formatted data string
        """
        if format_type == "json":
            import json

            data = [trial.model_dump() for trial in trial_data_list]
            return json.dumps(data, indent=2, default=str)
        elif format_type == "csv":
            import csv
            import io

            if not trial_data_list:
                return ""

            # Get field names from the first trial
            fieldnames = list(trial_data_list[0].model_dump().keys())

            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()

            for trial in trial_data_list:
                writer.writerow(trial.model_dump())

            return output.getvalue()
        else:
            raise ValueError(f"Unsupported format type: {format_type}")

    def get_service_statistics(self) -> dict[str, Any]:
        """Get statistics about the clinical extraction service.

        Returns:
            Dictionary containing service statistics
        """
        return {
            "llm_provider": type(self.llm).__name__,
            "prompts_path": self.prompts_path,
            "available_prompts": self.langchain_clinical_service.get_service_statistics().get(
                "available_prompts", []
            ),
            "quality_thresholds": self.data_processor.quality_thresholds,
        }
