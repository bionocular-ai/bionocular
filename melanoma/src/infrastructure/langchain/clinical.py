"""LangChain-based clinical data extraction service.

This module provides sophisticated clinical data extraction capabilities using
LangChain's structured output features and custom clinical prompts for
oncology abstract processing.
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

from langchain_core.language_models import BaseLLM
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from ...domain.models import ChunkWithEmbedding

logger = logging.getLogger(__name__)


class ClinicalTrialData(BaseModel):
    """Structured clinical trial data extracted from abstracts.

    This model defines the structure for clinical trial data extraction,
    ensuring consistent and validated data format.
    """

    # Basic trial information
    trial_id: Optional[str] = Field(None, description="Clinical trial ID (NCT number)")
    abstract_id: Optional[str] = Field(None, description="Abstract ID")
    title: Optional[str] = Field(None, description="Trial title")

    # Study design
    study_design: Optional[str] = Field(None, description="Study design type")
    phase: Optional[str] = Field(None, description="Clinical trial phase")
    randomization: Optional[str] = Field(None, description="Randomization method")

    # Patient population
    patient_population: Optional[str] = Field(
        None, description="Patient population description"
    )
    inclusion_criteria: Optional[str] = Field(None, description="Inclusion criteria")
    exclusion_criteria: Optional[str] = Field(None, description="Exclusion criteria")

    # Treatment arms
    treatment_arms: list[str] = Field(
        default_factory=list, description="Treatment arms"
    )
    control_arm: Optional[str] = Field(None, description="Control arm description")
    experimental_arm: Optional[str] = Field(
        None, description="Experimental arm description"
    )

    # Endpoints
    primary_endpoint: Optional[str] = Field(None, description="Primary endpoint")
    secondary_endpoints: list[str] = Field(
        default_factory=list, description="Secondary endpoints"
    )

    # Results
    efficacy_results: Optional[str] = Field(None, description="Efficacy results")
    safety_results: Optional[str] = Field(None, description="Safety results")
    response_rate: Optional[str] = Field(None, description="Response rate")
    survival_data: Optional[str] = Field(None, description="Survival data")

    # Sponsor and funding
    sponsor: Optional[str] = Field(None, description="Study sponsor")
    funding_source: Optional[str] = Field(None, description="Funding source")

    # Additional information
    conference: Optional[str] = Field(None, description="Conference name")
    year: Optional[int] = Field(None, description="Conference year")
    doi: Optional[str] = Field(None, description="DOI reference")

    # Quality indicators
    confidence_score: Optional[float] = Field(
        None, description="Extraction confidence score"
    )
    extraction_notes: Optional[str] = Field(None, description="Extraction notes")


class ClinicalPromptManager:
    """Manages clinical data extraction prompts.

    This class encapsulates all prompt management logic for clinical data
    extraction, including template creation, validation, and rendering.
    """

    # Clinical data extraction prompts
    CLINICAL_PROMPTS = {
        "trial_extraction": """
You are a medical research assistant specializing in clinical trial data extraction.
Extract structured clinical trial information from the following oncology abstract.

Abstract Text:
{abstract_text}

Extract the following information:
1. Clinical Trial ID (NCT number)
2. Abstract ID
3. Trial Title
4. Study Design (randomized, phase, etc.)
5. Patient Population
6. Treatment Arms
7. Primary and Secondary Endpoints
8. Efficacy Results
9. Safety Results
10. Sponsor Information
11. Conference and Year
12. DOI Reference

Format the response as structured JSON with the following fields:
- trial_id: Clinical trial ID (NCT number)
- abstract_id: Abstract ID
- title: Trial title
- study_design: Study design type
- phase: Clinical trial phase
- randomization: Randomization method
- patient_population: Patient population description
- inclusion_criteria: Inclusion criteria
- exclusion_criteria: Exclusion criteria
- treatment_arms: List of treatment arms
- control_arm: Control arm description
- experimental_arm: Experimental arm description
- primary_endpoint: Primary endpoint
- secondary_endpoints: List of secondary endpoints
- efficacy_results: Efficacy results
- safety_results: Safety results
- response_rate: Response rate
- survival_data: Survival data
- sponsor: Study sponsor
- funding_source: Funding source
- conference: Conference name
- year: Conference year
- doi: DOI reference
- confidence_score: Extraction confidence (0.0-1.0)
- extraction_notes: Any notes about the extraction

If information is not available, use null for that field.
""",
        "safety_analysis": """
Analyze the safety profile from the following clinical trial text:

Trial Text:
{trial_text}

Extract and analyze:
1. Adverse Events (AEs)
2. Serious Adverse Events (SAEs)
3. Treatment-related AEs
4. Grade 3/4 AEs
5. Safety conclusions
6. Risk-benefit assessment

Format as structured JSON.
""",
        "efficacy_analysis": """
Analyze the efficacy results from the following clinical trial text:

Trial Text:
{trial_text}

Extract and analyze:
1. Primary endpoint results
2. Secondary endpoint results
3. Response rates
4. Survival data (PFS, OS)
5. Statistical significance
6. Clinical significance

Format as structured JSON.
""",
    }

    def __init__(self, prompts_path: Optional[str] = None):
        """Initialize the clinical prompt manager.

        Args:
            prompts_path: Path to custom prompts file
        """
        self._templates: dict[str, PromptTemplate] = {}
        self._load_default_prompts()

        if prompts_path:
            self._load_custom_prompts(prompts_path)

    def _load_default_prompts(self) -> None:
        """Load default clinical prompts."""
        for name, template in self.CLINICAL_PROMPTS.items():
            self._templates[name] = PromptTemplate(
                template=template,
                input_variables=self._extract_input_variables(template),
            )
        logger.info(f"Loaded {len(self.CLINICAL_PROMPTS)} default clinical prompts")

    def _load_custom_prompts(self, prompts_path: str) -> None:
        """Load custom prompts from file.

        Args:
            prompts_path: Path to prompts file
        """
        try:
            prompts_file = Path(prompts_path)
            if not prompts_file.exists():
                logger.warning(f"Prompts file not found: {prompts_path}")
                return

            with open(prompts_file) as f:
                custom_prompts = json.load(f)

            for name, template in custom_prompts.items():
                self._templates[name] = PromptTemplate(
                    template=template,
                    input_variables=self._extract_input_variables(template),
                )

            logger.info(
                f"Loaded {len(custom_prompts)} custom clinical prompts from {prompts_path}"
            )

        except Exception as e:
            logger.error(f"Failed to load custom prompts: {e}")
            raise RuntimeError(f"Custom prompts loading failed: {e}") from e

    def _extract_input_variables(self, template: str) -> list[str]:
        """Extract input variables from template string.

        Args:
            template: Template string

        Returns:
            List of input variable names
        """
        import re

        variables = re.findall(r"\{(\w+)\}", template)
        return list(set(variables))

    def get_prompt(self, name: str) -> PromptTemplate:
        """Get a prompt template by name.

        Args:
            name: Name of the prompt

        Returns:
            Prompt template

        Raises:
            ValueError: If prompt not found
        """
        if name not in self._templates:
            raise ValueError(f"Prompt '{name}' not found")
        return self._templates[name]

    def list_prompts(self) -> list[str]:
        """List available prompt templates.

        Returns:
            List of prompt names
        """
        return list(self._templates.keys())


class ClinicalDataExtractor:
    """Extracts clinical data from oncology abstracts.

    This class encapsulates all clinical data extraction logic including
    structured output parsing, validation, and quality assessment.
    """

    def __init__(self, llm: BaseLLM, prompt_manager: ClinicalPromptManager):
        """Initialize the clinical data extractor.

        Args:
            llm: LLM instance for data extraction
            prompt_manager: Clinical prompt manager
        """
        self.llm = llm
        self.prompt_manager = prompt_manager
        self.output_parser = PydanticOutputParser(pydantic_object=ClinicalTrialData)

        logger.info("Clinical data extractor initialized")

    async def extract_trial_data(self, abstract_text: str) -> ClinicalTrialData:
        """Extract clinical trial data from abstract text.

        Args:
            abstract_text: Abstract text to extract data from

        Returns:
            Extracted clinical trial data

        Raises:
            RuntimeError: If extraction fails
        """
        try:
            # Get the trial extraction prompt
            prompt = self.prompt_manager.get_prompt("trial_extraction")

            # Format the prompt
            formatted_prompt = prompt.format(abstract_text=abstract_text)

            # Generate response
            response = self.llm.invoke(formatted_prompt)

            # Parse the response
            trial_data = self._parse_trial_data(response)

            # Calculate confidence score
            trial_data.confidence_score = self._calculate_confidence_score(trial_data)

            logger.info(
                f"Successfully extracted trial data with confidence: {trial_data.confidence_score}"
            )
            return trial_data

        except Exception as e:
            logger.error(f"Trial data extraction failed: {e}")
            raise RuntimeError(f"Trial data extraction failed: {e}") from e

    def _parse_trial_data(self, response: str) -> ClinicalTrialData:
        """Parse trial data from LLM response.

        Args:
            response: LLM response text

        Returns:
            Parsed clinical trial data
        """
        try:
            # Try to parse as JSON
            if response.strip().startswith("{"):
                data = json.loads(response)
                return ClinicalTrialData(**data)
            else:
                # Fallback: create basic data structure
                return ClinicalTrialData(
                    extraction_notes=f"Raw response: {response[:200]}...",
                    confidence_score=0.3,
                )
        except Exception as e:
            logger.warning(f"Failed to parse trial data: {e}")
            return ClinicalTrialData(
                extraction_notes=f"Parse error: {str(e)}", confidence_score=0.1
            )

    def _calculate_confidence_score(self, trial_data: ClinicalTrialData) -> float:
        """Calculate confidence score for extracted data.

        Args:
            trial_data: Extracted trial data

        Returns:
            Confidence score between 0.0 and 1.0
        """
        score = 0.0
        total_fields = 0

        # Check for key fields
        key_fields = [
            "trial_id",
            "title",
            "study_design",
            "treatment_arms",
            "primary_endpoint",
            "efficacy_results",
            "safety_results",
        ]

        for field in key_fields:
            total_fields += 1
            value = getattr(trial_data, field)
            if (
                value
                and (isinstance(value, str) and value.strip())
                or (isinstance(value, list) and value)
            ):
                score += 1.0

        # Check for additional fields
        additional_fields = ["phase", "patient_population", "sponsor", "conference"]

        for field in additional_fields:
            total_fields += 1
            value = getattr(trial_data, field)
            if (
                value
                and (isinstance(value, str) and value.strip())
                or (isinstance(value, list) and value)
            ):
                score += 0.5

        return min(score / total_fields, 1.0) if total_fields > 0 else 0.0

    async def extract_safety_data(self, trial_text: str) -> dict[str, Any]:
        """Extract safety data from trial text.

        Args:
            trial_text: Trial text to extract safety data from

        Returns:
            Extracted safety data
        """
        try:
            prompt = self.prompt_manager.get_prompt("safety_analysis")
            formatted_prompt = prompt.format(trial_text=trial_text)
            response = self.llm.invoke(formatted_prompt)

            # Parse JSON response
            if response.strip().startswith("{"):
                return json.loads(response)
            else:
                return {"raw_response": response, "confidence": 0.3}

        except Exception as e:
            logger.error(f"Safety data extraction failed: {e}")
            return {"error": str(e), "confidence": 0.0}

    async def extract_efficacy_data(self, trial_text: str) -> dict[str, Any]:
        """Extract efficacy data from trial text.

        Args:
            trial_text: Trial text to extract efficacy data from

        Returns:
            Extracted efficacy data
        """
        try:
            prompt = self.prompt_manager.get_prompt("efficacy_analysis")
            formatted_prompt = prompt.format(trial_text=trial_text)
            response = self.llm.invoke(formatted_prompt)

            # Parse JSON response
            if response.strip().startswith("{"):
                return json.loads(response)
            else:
                return {"raw_response": response, "confidence": 0.3}

        except Exception as e:
            logger.error(f"Efficacy data extraction failed: {e}")
            return {"error": str(e), "confidence": 0.0}


class LangChainClinicalService:
    """LangChain-based clinical data extraction service.

    This service provides sophisticated clinical data extraction capabilities
    using LangChain's structured output features and custom clinical prompts
    for oncology abstract processing.
    """

    def __init__(self, llm: BaseLLM, prompts_path: Optional[str] = None):
        """Initialize the LangChain clinical service.

        Args:
            llm: LLM instance for data extraction
            prompts_path: Path to custom prompts file
        """
        self.llm = llm
        self.prompt_manager = ClinicalPromptManager(prompts_path)
        self.data_extractor = ClinicalDataExtractor(llm, self.prompt_manager)

        logger.info("LangChain clinical service initialized")

    async def extract_clinical_data(
        self, chunks: list[ChunkWithEmbedding]
    ) -> list[ClinicalTrialData]:
        """Extract clinical data from chunks.

        Args:
            chunks: List of chunks to extract data from

        Returns:
            List of extracted clinical trial data
        """
        try:
            # Combine chunks into abstract text
            abstract_text = self._combine_chunks(chunks)

            # Extract trial data
            trial_data = await self.data_extractor.extract_trial_data(abstract_text)

            # Extract additional safety and efficacy data
            safety_data = await self.data_extractor.extract_safety_data(abstract_text)
            efficacy_data = await self.data_extractor.extract_efficacy_data(
                abstract_text
            )

            # Enhance trial data with additional information
            trial_data.extraction_notes = f"Safety: {safety_data.get('confidence', 0.0):.2f}, Efficacy: {efficacy_data.get('confidence', 0.0):.2f}"

            logger.info(
                f"Successfully extracted clinical data from {len(chunks)} chunks"
            )
            return [trial_data]

        except Exception as e:
            logger.error(f"Clinical data extraction failed: {e}")
            raise RuntimeError(f"Clinical data extraction failed: {e}") from e

    def _combine_chunks(self, chunks: list[ChunkWithEmbedding]) -> str:
        """Combine chunks into abstract text.

        Args:
            chunks: List of chunks to combine

        Returns:
            Combined abstract text
        """
        # Sort chunks by sequence number
        sorted_chunks = sorted(chunks, key=lambda x: x.sequence_number)

        # Combine content
        abstract_parts = []
        for chunk in sorted_chunks:
            abstract_parts.append(chunk.content)

        return "\n\n".join(abstract_parts)

    def get_service_statistics(self) -> dict[str, Any]:
        """Get statistics about the clinical service.

        Returns:
            Dictionary containing service statistics
        """
        return {
            "available_prompts": self.prompt_manager.list_prompts(),
            "total_prompts": len(self.prompt_manager.list_prompts()),
            "llm_provider": type(self.llm).__name__,
        }
