"""Clinical data extraction API endpoints.

This module provides FastAPI endpoints for clinical data extraction from
oncology abstracts using LangChain's structured output capabilities.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..domain.clinical_trial_models import ClinicalTrialData
from .clinical_extraction_service import ClinicalExtractionService
from .langchain_factory_service import LangChainServiceFactory, ServiceConfiguration
from .pipeline_service import EndToEndPipelineService

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/clinical", tags=["clinical-extraction"])


# Request/Response models
class ClinicalExtractionRequest(BaseModel):
    """Request model for clinical data extraction."""

    text: str
    enrich_data: bool = True
    validate_data: bool = True


class ClinicalExtractionResponse(BaseModel):
    """Response model for clinical data extraction."""

    trial_data: dict[str, Any]
    validation_results: Optional[dict[str, Any]] = None
    quality_score: Optional[float] = None
    extraction_notes: Optional[str] = None


class BatchClinicalExtractionRequest(BaseModel):
    """Request model for batch clinical data extraction."""

    texts: list[str]
    enrich_data: bool = True
    validate_data: bool = True


class BatchClinicalExtractionResponse(BaseModel):
    """Response model for batch clinical data extraction."""

    results: list[dict[str, Any]]
    statistics: dict[str, Any]
    total_processed: int
    successful_extractions: int
    failed_extractions: int


class ClinicalValidationRequest(BaseModel):
    """Request model for clinical data validation."""

    trial_data: dict[str, Any]


class ClinicalValidationResponse(BaseModel):
    """Response model for clinical data validation."""

    is_valid: bool
    quality_score: float
    quality_level: str
    missing_fields: list[str]
    quality_issues: list[str]
    recommendations: list[str]


class ClinicalExportRequest(BaseModel):
    """Request model for clinical data export."""

    trial_data_list: list[dict[str, Any]]
    format_type: str = "json"  # json or csv


class ClinicalExportResponse(BaseModel):
    """Response model for clinical data export."""

    data: str
    format_type: str
    total_records: int


# Service factory instance
_service_factory: Optional[LangChainServiceFactory] = None


def get_service_factory() -> LangChainServiceFactory:
    """Get service factory instance."""
    global _service_factory
    if _service_factory is None:
        # Configure service factory with clinical-focused settings
        config = ServiceConfiguration(
            chunking_strategy="header_based",
            embedding_model="pritamdeka/S-BioBERT-snli-multinli-stsb",
            llm_provider="openai",
            llm_model="gpt-3.5-turbo",
            temperature=0.1,
            persist_directory="./langchain_chroma_db",
            collection_name="melanoma_chunks",
        )
        _service_factory = LangChainServiceFactory(config)
    return _service_factory


def get_clinical_service() -> ClinicalExtractionService:
    """Get clinical extraction service instance."""
    try:
        factory = get_service_factory()
        return factory.create_clinical_service()
    except Exception as e:
        logger.error(f"Failed to create clinical service: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to initialize clinical service: {e}"
        ) from e


def get_pipeline_service() -> EndToEndPipelineService:
    """Get end-to-end pipeline service instance."""
    try:
        factory = get_service_factory()
        return factory.create_pipeline_service()
    except Exception as e:
        logger.error(f"Failed to create pipeline service: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to initialize pipeline service: {e}"
        ) from e


# API Endpoints
@router.post("/extract", response_model=ClinicalExtractionResponse)
async def extract_clinical_data(
    request: ClinicalExtractionRequest,
    clinical_service: ClinicalExtractionService = Depends(get_clinical_service),
) -> ClinicalExtractionResponse:
    """Extract clinical trial data from text.

    Args:
        request: Clinical extraction request
        clinical_service: Injected clinical service

    Returns:
        Extracted clinical trial data

    Raises:
        HTTPException: If extraction fails
    """
    try:
        logger.info("Starting clinical data extraction")

        # Extract clinical data
        trial_data_list = await clinical_service.extract_trial_data_from_text(
            text=request.text,
            enrich_data=request.enrich_data,
            validate_data=request.validate_data,
        )

        if not trial_data_list:
            raise HTTPException(
                status_code=400,
                detail="No clinical data could be extracted from the provided text",
            )

        trial_data = trial_data_list[0]

        # Get validation results if validation was performed
        validation_results = None
        if request.validate_data:
            from .clinical_extraction_service import ClinicalDataProcessor

            processor = ClinicalDataProcessor()
            validation_results = processor.validate_trial_data(trial_data)

        # Format response
        response = ClinicalExtractionResponse(
            trial_data=trial_data.model_dump(),
            validation_results=validation_results,
            quality_score=trial_data.confidence_score,
            extraction_notes=trial_data.extraction_notes,
        )

        logger.info(
            f"Clinical data extraction completed with quality score: {trial_data.confidence_score}"
        )
        return response

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Clinical data extraction failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Clinical data extraction failed: {e}"
        ) from e


@router.post("/extract/batch", response_model=BatchClinicalExtractionResponse)
async def extract_clinical_data_batch(
    request: BatchClinicalExtractionRequest,
    clinical_service: ClinicalExtractionService = Depends(get_clinical_service),
) -> BatchClinicalExtractionResponse:
    """Extract clinical trial data from multiple texts.

    Args:
        request: Batch clinical extraction request
        clinical_service: Injected clinical service

    Returns:
        Batch extraction results

    Raises:
        HTTPException: If batch extraction fails
    """
    try:
        logger.info(
            f"Starting batch clinical data extraction for {len(request.texts)} texts"
        )

        # Process each text
        results = []
        successful_extractions = 0
        failed_extractions = 0

        for i, text in enumerate(request.texts):
            try:
                trial_data_list = await clinical_service.extract_trial_data_from_text(
                    text=text,
                    enrich_data=request.enrich_data,
                    validate_data=request.validate_data,
                )

                if trial_data_list:
                    results.append(
                        {
                            "index": i,
                            "success": True,
                            "trial_data": trial_data_list[0].model_dump(),
                            "quality_score": trial_data_list[0].confidence_score,
                        }
                    )
                    successful_extractions += 1
                else:
                    results.append(
                        {
                            "index": i,
                            "success": False,
                            "error": "No clinical data could be extracted",
                        }
                    )
                    failed_extractions += 1

            except Exception as e:
                results.append(
                    {
                        "index": i,
                        "success": False,
                        "error": str(e),
                    }
                )
                failed_extractions += 1

        # Calculate statistics
        statistics = clinical_service.get_extraction_statistics(
            [
                ClinicalTrialData(**result["trial_data"])
                for result in results
                if result["success"]
            ]
        )

        response = BatchClinicalExtractionResponse(
            results=results,
            statistics=statistics,
            total_processed=len(request.texts),
            successful_extractions=successful_extractions,
            failed_extractions=failed_extractions,
        )

        logger.info(
            f"Batch clinical data extraction completed: {successful_extractions} successful, {failed_extractions} failed"
        )
        return response

    except Exception as e:
        logger.error(f"Batch clinical data extraction failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Batch clinical data extraction failed: {e}"
        ) from e


@router.post("/validate", response_model=ClinicalValidationResponse)
async def validate_clinical_data(
    request: ClinicalValidationRequest,
    clinical_service: ClinicalExtractionService = Depends(get_clinical_service),
) -> ClinicalValidationResponse:
    """Validate clinical trial data quality.

    Args:
        request: Clinical validation request
        clinical_service: Injected clinical service

    Returns:
        Validation results

    Raises:
        HTTPException: If validation fails
    """
    try:
        # Convert dict to ClinicalTrialData
        trial_data = ClinicalTrialData(**request.trial_data)

        # Validate data
        from .clinical_extraction_service import ClinicalDataProcessor

        processor = ClinicalDataProcessor()
        validation_results = processor.validate_trial_data(trial_data)

        response = ClinicalValidationResponse(
            is_valid=validation_results["is_valid"],
            quality_score=validation_results["quality_score"],
            quality_level=validation_results["quality_level"],
            missing_fields=validation_results["missing_fields"],
            quality_issues=validation_results["quality_issues"],
            recommendations=validation_results["recommendations"],
        )

        logger.info(
            f"Clinical data validation completed: {validation_results['quality_level']} quality"
        )
        return response

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Clinical data validation failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Clinical data validation failed: {e}"
        ) from e


@router.post("/export", response_model=ClinicalExportResponse)
async def export_clinical_data(
    request: ClinicalExportRequest,
    clinical_service: ClinicalExtractionService = Depends(get_clinical_service),
) -> ClinicalExportResponse:
    """Export clinical trial data in various formats.

    Args:
        request: Clinical export request
        clinical_service: Injected clinical service

    Returns:
        Exported data

    Raises:
        HTTPException: If export fails
    """
    try:
        # Convert dicts to ClinicalTrialData objects
        trial_data_list = [
            ClinicalTrialData(**data) for data in request.trial_data_list
        ]

        # Format data
        formatted_data = clinical_service.format_trial_data_for_export(
            trial_data_list, request.format_type
        )

        response = ClinicalExportResponse(
            data=formatted_data,
            format_type=request.format_type,
            total_records=len(trial_data_list),
        )

        logger.info(
            f"Clinical data exported: {len(trial_data_list)} records in {request.format_type} format"
        )
        return response

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Clinical data export failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Clinical data export failed: {e}"
        ) from e


@router.post("/process-document")
async def process_document_with_clinical_extraction(
    content: str,
    filename: str = "",
    document_id: Optional[str] = None,
    extract_clinical_data: bool = True,
    pipeline_service: EndToEndPipelineService = Depends(get_pipeline_service),
) -> dict[str, Any]:
    """Process a document with clinical data extraction.

    Args:
        content: Document content
        filename: Filename for metadata
        document_id: Document ID
        extract_clinical_data: Whether to extract clinical data
        pipeline_service: Injected pipeline service

    Returns:
        Processing results with clinical data

    Raises:
        HTTPException: If processing fails
    """
    try:
        logger.info(f"Processing document with clinical extraction: {filename}")

        # Process document through pipeline
        results = await pipeline_service.process_document(
            content=content,
            filename=filename,
            document_id=document_id,
            extract_clinical_data=extract_clinical_data,
        )

        logger.info(
            f"Document processing completed: {results['chunks_created']} chunks, {results['clinical_trials_found']} trials"
        )
        return results

    except Exception as e:
        logger.error(f"Document processing with clinical extraction failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Document processing failed: {e}"
        ) from e


@router.get("/statistics")
async def get_clinical_statistics(
    clinical_service: ClinicalExtractionService = Depends(get_clinical_service),
) -> dict[str, Any]:
    """Get clinical extraction service statistics.

    Args:
        clinical_service: Injected clinical service

    Returns:
        Service statistics
    """
    try:
        statistics = clinical_service.get_service_statistics()
        return statistics

    except Exception as e:
        logger.error(f"Failed to get clinical statistics: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get clinical statistics: {e}"
        ) from e


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint for clinical services.

    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "service": "clinical-extraction",
        "version": "1.0.0",
        "endpoints": [
            "/extract",
            "/extract/batch",
            "/validate",
            "/export",
            "/process-document",
            "/statistics",
        ],
    }
