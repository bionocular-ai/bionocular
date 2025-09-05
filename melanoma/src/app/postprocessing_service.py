"""Postprocessing service for orchestrating conference abstract processing."""

import logging
import re
from pathlib import Path

from domain.interfaces import PostprocessingServiceInterface, PostprocessorInterface
from domain.models import (
    ConferenceType,
    PostprocessingConfiguration,
    PostprocessingResult,
)
from infrastructure.asco_postprocessor import ASCOPostprocessor
from infrastructure.esmo_postprocessor import ESMOPostprocessor

logger = logging.getLogger(__name__)


class PostprocessingService(PostprocessingServiceInterface):
    """Service for orchestrating conference abstract postprocessing."""

    def __init__(self):
        """Initialize the postprocessing service."""
        self.processors: dict[ConferenceType, PostprocessorInterface] = {
            ConferenceType.ASCO: ASCOPostprocessor(),
            ConferenceType.ESMO: ESMOPostprocessor(),
        }

    def _get_processor(self, conference_type: ConferenceType) -> PostprocessorInterface:
        """Get the appropriate processor for a conference type."""
        if conference_type not in self.processors:
            raise ValueError(f"Unsupported conference type: {conference_type}")
        return self.processors[conference_type]

    def _split_abstracts(
        self, content: str, conference_type: ConferenceType
    ) -> list[str]:
        """Split raw content into individual abstracts."""
        if conference_type == ConferenceType.ASCO:
            # ASCO format: Split by {N}------------------------------------------------
            abstracts = re.split(
                r"\{\d+\}------------------------------------------------", content
            )
            return [abstract.strip() for abstract in abstracts if abstract.strip()]

        elif conference_type == ConferenceType.ESMO:
            # ESMO format: Split by DOI links and titles
            # This is a simplified version - the actual ESMO processor handles this more robustly

            # Step 1: Split by DOI links (primary separator)
            doi_pattern = r"(?=https://doi\.org/\[?10\.1016/j\.annonc\.\d{4}\.\d{2}\.\d{4}\]?\(https://doi\.org/10\.1016/j\.annonc\.\d{4}\.\d{2}\.\d{4}\))"
            doi_splits = re.split(doi_pattern, content, flags=re.MULTILINE)

            # Step 2: For parts without DOI, split by titles
            abstract_texts = []
            for part in doi_splits:
                if not part.strip():
                    continue

                # Look for multiple abstracts in this part
                title_pattern = r"(?=^(?:#|##|###|####)\s*(1\d{3}[A-Z]*|[78]\d{2}(?:O|MO|P|TiP))\s+|^1\d{3}[A-Z]*\s+|^[78]\d{2}(?:O|MO|P|TiP)\s+)"
                title_splits = re.split(title_pattern, part, flags=re.MULTILINE)

                for split in title_splits:
                    if split and split.strip():
                        # Clean DOI prefixes
                        cleaned_split = split.strip()
                        cleaned_split = re.sub(
                            r"^https://doi\.org/\[?10\.1016/j\.annonc\.\d{4}\.\d{2}\.\d{4}\]?\(https://doi\.org/10\.1016/j\.annonc\.\d{4}\.\d{2}\.\d{4}\)\s*\n*",
                            "",
                            cleaned_split,
                        )

                        if cleaned_split.strip():
                            abstract_texts.append(cleaned_split.strip())

            # Filter out very short or invalid blocks
            filtered_abstracts = []
            for text in abstract_texts:
                if len(text.strip()) > 100 and (
                    "background:" in text.lower()
                    or re.search(r"1\d{3}(?:[A-Z]+|TiP)|[78]\d{2}(?:O|MO|P|TiP)", text)
                    or text.count("\n") > 5
                ):
                    filtered_abstracts.append(text)

            return filtered_abstracts

        else:
            raise ValueError(f"Unsupported conference type: {conference_type}")

    async def process_file(
        self, input_path: str, output_path: str, config: PostprocessingConfiguration
    ) -> PostprocessingResult:
        """Process a single file containing conference abstracts."""
        try:
            logger.info(f"Processing file: {input_path}")

            # Read input file
            input_file = Path(input_path)
            if not input_file.exists():
                raise FileNotFoundError(f"Input file not found: {input_path}")

            with open(input_file, encoding="utf-8") as f:
                content = f.read()

            # Get the appropriate processor
            processor = self._get_processor(config.conference_type)

            # Split content into individual abstracts
            abstract_texts = self._split_abstracts(content, config.conference_type)
            logger.info(f"Found {len(abstract_texts)} abstracts to process")

            # Process each abstract
            formatted_abstracts = []
            abstracts_with_warnings = 0
            structured_metadata_count = 0
            conference_specific_features = 0
            errors = []

            for i, abstract_text in enumerate(abstract_texts):
                try:
                    # Parse the abstract
                    parsed_abstract = await processor.parse_abstract(abstract_text)

                    # Validate the abstract
                    validation_issues = await processor.validate_abstract(
                        parsed_abstract
                    )
                    if validation_issues:
                        abstracts_with_warnings += 1
                        logger.warning(
                            f"Abstract {parsed_abstract.id}: {', '.join(validation_issues)}"
                        )

                    # Count structured metadata
                    if any(
                        [
                            parsed_abstract.clinical_trial_info,
                            parsed_abstract.sponsor,
                            parsed_abstract.legal_entity,
                            parsed_abstract.funding,
                            parsed_abstract.doi,
                        ]
                    ):
                        structured_metadata_count += 1

                    # Count conference-specific features
                    if config.conference_type == ConferenceType.ESMO:
                        if (
                            parsed_abstract.trial_design
                            or parsed_abstract.doi
                            or parsed_abstract.legal_entity
                        ):
                            conference_specific_features += 1
                    elif config.conference_type == ConferenceType.ASCO:
                        if (
                            parsed_abstract.full_text_reference
                            or "TPS" in parsed_abstract.id
                        ):
                            conference_specific_features += 1

                    # Format to markdown
                    formatted_md = await processor.format_to_markdown(
                        parsed_abstract, config
                    )
                    formatted_abstracts.append(formatted_md)

                except Exception as e:
                    error_msg = f"Error processing abstract {i+1}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)

            # Write output file
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, "w", encoding="utf-8") as f:
                f.write("\n\n---\n\n".join(formatted_abstracts))

            # Validate the output file
            validation_summary = await self.validate_file(output_path)

            result = PostprocessingResult(
                success=True,
                abstracts_processed=len(formatted_abstracts),
                abstracts_with_warnings=abstracts_with_warnings,
                structured_metadata_count=structured_metadata_count,
                conference_specific_features=conference_specific_features,
                output_path=output_path,
                validation_summary=validation_summary,
                errors=errors,
            )

            logger.info(
                f"Processing completed: {len(formatted_abstracts)} abstracts processed"
            )
            return result

        except Exception as e:
            logger.error(f"Processing failed: {str(e)}")
            return PostprocessingResult(
                success=False,
                abstracts_processed=0,
                abstracts_with_warnings=0,
                structured_metadata_count=0,
                conference_specific_features=0,
                output_path=output_path,
                validation_summary={},
                errors=[str(e)],
            )

    async def process_batch(
        self,
        input_paths: list[str],
        output_dir: str,
        config: PostprocessingConfiguration,
    ) -> list[PostprocessingResult]:
        """Process multiple files in batch."""
        results = []
        output_directory = Path(output_dir)
        output_directory.mkdir(parents=True, exist_ok=True)

        for input_path in input_paths:
            input_file = Path(input_path)
            output_file = output_directory / f"enhanced_{input_file.name}"

            result = await self.process_file(input_path, str(output_file), config)
            results.append(result)

        return results

    async def validate_file(self, file_path: str) -> dict[str, any]:
        """Validate a processed file and return validation summary."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            abstracts = content.split("\n\n---\n\n")
            total_abstracts = len(abstracts)
            warnings = 0

            # Count different types of abstracts and features
            structured_metadata_count = 0
            conference_features = {
                "tps_abstracts": 0,
                "full_text_references": 0,
                "trial_design_sections": 0,
                "doi_links": 0,
            }

            # Check for structured headers vs legacy inline format
            structured_sections = [
                "#### Clinical Trial Information:",
                "#### Research Sponsor:",
                "#### Clinical Trial Identification:",
                "#### Legal Entity Responsible for Study:",
                "#### Funding:",
                "#### DOI:",
                "#### Study Results:",
            ]

            for abstract in abstracts:
                # Count structured metadata
                metadata_present = any(
                    section in abstract for section in structured_sections
                )
                if metadata_present:
                    structured_metadata_count += 1

                # Count conference-specific features
                if "TPS" in abstract:
                    conference_features["tps_abstracts"] += 1
                if "#### Full Text Reference:" in abstract:
                    conference_features["full_text_references"] += 1
                if "#### Trial Design:" in abstract:
                    conference_features["trial_design_sections"] += 1
                if "#### DOI:" in abstract:
                    conference_features["doi_links"] += 1

                # Basic validation
                if "### Abstract ID:" not in abstract:
                    warnings += 1
                if "**Title:** N/A" in abstract:
                    warnings += 1

            rag_optimization = (
                "Enhanced"
                if structured_metadata_count > total_abstracts * 0.8
                else "Basic"
            )

            return {
                "total_abstracts": total_abstracts,
                "abstracts_with_warnings": warnings,
                "structured_metadata_count": structured_metadata_count,
                "rag_optimization": rag_optimization,
                "conference_features": conference_features,
                "validation_status": "Passed" if warnings == 0 else "Warnings",
            }

        except Exception as e:
            return {"error": str(e), "validation_status": "Failed"}
