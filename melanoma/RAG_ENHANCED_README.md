# RAG-Enhanced Clinical Trial Extraction

## Overview

This implementation provides a sophisticated RAG-enhanced extraction workflow that combines treatment arm separation with targeted attribute extraction to improve quality and reduce hallucination in clinical trial data extraction.

## Architecture

### Core Components

1. **Treatment Arm Separator** (`treatment_arm_separator.py`)
   - Uses LLM to identify and separate treatment arms from abstracts
   - Provides structured output with arm metadata
   - Validates separation quality

2. **Arm-Aware RAG Provider** (`arm_aware_rag_provider.py`)
   - Retrieves targeted context for specific treatment arms
   - Generates arm-specific queries for better precision
   - Provides context quality assessment

3. **RAG-Enhanced Extraction Service** (`rag_enhanced_extraction_service.py`)
   - Orchestrates the complete workflow
   - Combines treatment arm separation with attribute extraction
   - Provides quality assessment and validation

4. **Treatment Arm Models** (`treatment_arm_models.py`)
   - Domain models for treatment arms and extraction results
   - Validation rules and quality assessment models

## Workflow

### Phase 1: Document Processing
```
Abstract Input → Chunking → Embedding → Vector Storage
```

### Phase 2: Treatment Arm Separation
```
Full Abstract → LLM Analysis → Treatment Arms Identified
```

### Phase 3: RAG-Enhanced Attribute Extraction
```
For Each Treatment Arm:
  → RAG Context Retrieval
  → Targeted Attribute Extraction
  → Validation & Quality Assessment
```

### Phase 4: Results Consolidation
```
Arm Results → Quality Assessment → Final Results
```

## Key Features

### 1. Treatment Arm Separation
- **Automatic Detection**: Identifies treatment arms using LLM analysis
- **Arm Classification**: Categorizes arms (monotherapy, combination, dose variations)
- **Metadata Extraction**: Extracts arm-specific information (drug names, doses, patient counts)
- **Quality Validation**: Validates separation quality and completeness

### 2. RAG-Enhanced Context Retrieval
- **Arm-Specific Queries**: Generates targeted queries for each arm and attribute
- **Context Quality Assessment**: Evaluates relevance and quality of retrieved context
- **Deduplication**: Prevents duplicate context chunks
- **Similarity Scoring**: Ranks context by relevance

### 3. Targeted Attribute Extraction
- **Arm-Aware Extraction**: Extracts attributes with arm-specific context
- **Confidence Scoring**: Provides confidence scores for each extraction
- **Validation**: Validates extracted values against expected formats
- **Error Handling**: Graceful handling of extraction failures

### 4. Quality Assessment
- **Multi-Level Validation**: Validates at arm and attribute levels
- **Confidence Calculation**: Calculates overall extraction confidence
- **Quality Metrics**: Provides detailed quality assessment
- **Recommendations**: Suggests improvements for low-quality extractions

## Usage

### Basic Usage

```python
from src.app.rag_enhanced_extraction_service import RAGEnhancedExtractionService
from src.domain.extraction_models import AttributeType

# Initialize service
service = RAGEnhancedExtractionService(
    treatment_arm_separator=treatment_arm_separator,
    arm_aware_rag_provider=arm_aware_rag_provider,
    attribute_extractor=attribute_extractor,
    llm_service=llm_service
)

# Extract attributes
result = await service.extract_attributes_from_abstract(
    abstract_text=abstract_text,
    abstract_id="abstract_123",
    attributes=[
        AttributeType.NCT_NUMBER,
        AttributeType.GENERIC_NAME,
        AttributeType.P_VALUE_OS,
        AttributeType.OBJECTIVE_RESPONSE_RATE,
        AttributeType.GRADE_3_PLUS_AE
    ]
)
```

### Advanced Usage

```python
# Custom configuration
result = await service.extract_attributes_from_abstract(
    abstract_text=abstract_text,
    abstract_id="abstract_123",
    attributes=attributes,
    context_chunks_per_arm=10,  # More context chunks
    similarity_threshold=0.2    # Higher similarity threshold
)

# Quality assessment
quality = await service.validate_extraction_quality(result)
print(f"Quality Score: {quality['quality_score']:.3f}")

# Detailed statistics
stats = service.get_extraction_statistics(result)
print(f"Success Rate: {stats['success_rate']:.3f}")
```

## Configuration

### Service Configuration

```python
from src.app.langchain_factory_service import ServiceConfiguration

config = ServiceConfiguration(
    chunking_strategy="header_based",
    embedding_model="pritamdeka/S-BioBERT-snli-multinli-stsb",
    llm_provider="openai",
    llm_model="gpt-4o-mini",
    temperature=0.1,
    persist_directory="./chroma_db",
    collection_name="clinical_trials"
)
```

### Treatment Arm Separation

The treatment arm separator uses a sophisticated prompt to identify arms:

```python
TREATMENT_ARM_SEPARATION_PROMPT = """
TASK: Identify and separate treatment arms from this clinical trial abstract.

CRITICAL REQUIREMENTS:
1. Each unique treatment regimen is a separate arm
2. Different doses of the same drug are separate arms
3. Combination therapies are single arms with "+" notation
4. Extract arm-specific metadata (drug names, doses, patient counts)
5. Identify line of treatment and arm type

OUTPUT FORMAT (JSON):
{
  "treatment_arms": [
    {
      "arm_id": "arm_1",
      "arm_name": "Nivolumab 3mg/kg",
      "generic_name": "Nivolumab",
      "dose": "3mg/kg",
      "patient_count": 313,
      "line_of_treatment": "first_line",
      "arm_type": "monotherapy"
    }
  ]
}
"""
```

### RAG Context Retrieval

The arm-aware RAG provider generates targeted queries:

```python
# For NCT_NUMBER
queries = [
    "NCT number clinical trial identifier",
    "ClinicalTrials.gov registration number",
    "trial registration NCT"
]

# For GENERIC_NAME with specific arm
queries = [
    "generic drug name treatment arm Nivolumab",
    "medication name therapy Nivolumab 3mg/kg",
    "drug name treatment Nivolumab"
]
```

## Data Models

### Treatment Arm

```python
class TreatmentArm(BaseModel):
    arm_id: str
    arm_name: str
    generic_name: str
    dose: Optional[str]
    patient_count: Optional[int]
    line_of_treatment: LineOfTreatment
    arm_type: ArmType
    confidence_score: float
    # ... additional fields
```

### Extraction Result

```python
class TreatmentArmExtractionResult(BaseModel):
    abstract_id: str
    arm_results: Dict[str, Dict[str, Any]]
    overall_confidence: float
    processing_time_ms: int
    total_attributes_extracted: int
    # ... additional fields
```

## Quality Assessment

### Quality Metrics

1. **Separation Quality**: Confidence in treatment arm separation
2. **Context Quality**: Relevance and quality of retrieved context
3. **Extraction Quality**: Confidence in attribute extraction
4. **Overall Quality**: Combined quality score

### Quality Levels

- **High** (≥0.8): Excellent quality, ready for use
- **Medium** (0.6-0.8): Good quality, minor issues
- **Low** (<0.6): Poor quality, needs review

### Quality Issues

Common quality issues and recommendations:

- **Low separation confidence**: Check abstract quality, consider manual review
- **Incomplete arm information**: Improve arm metadata extraction
- **Poor context quality**: Adjust similarity thresholds, improve queries
- **Low extraction confidence**: Check LLM configuration, improve prompts

## Error Handling

### Treatment Arm Separation Failures
- Fallback to single-arm processing
- Manual review triggers
- Quality alerts for low-confidence separations

### RAG Context Retrieval Failures
- Fallback to full abstract context
- Alternative query strategies
- Context quality assessment

### Attribute Extraction Failures
- Retry with different prompts
- Manual extraction triggers
- Quality-based re-extraction

## Performance Optimization

### Parallel Processing
- Process treatment arms in parallel
- Batch RAG context retrieval
- Concurrent attribute extraction

### Caching Strategy
- Cache RAG context for similar queries
- Reuse treatment arm separations
- Store intermediate results

### Resource Management
- LLM rate limiting
- Vector database optimization
- Memory management for large documents

## Monitoring & Metrics

### Extraction Quality Metrics
- Attribute extraction success rate
- Confidence score distribution
- Validation failure rates

### Performance Metrics
- Processing time per abstract
- RAG context retrieval time
- LLM response times

### Quality Trends
- Quality score trends over time
- Common extraction failures
- Improvement opportunities

## Demo

Run the demo to see the workflow in action:

```bash
python demo_rag_enhanced_extraction.py
```

The demo will:
1. Process a sample melanoma abstract
2. Separate treatment arms
3. Extract attributes using RAG
4. Display results and quality metrics

## Benefits

### 1. Improved Precision
- RAG provides targeted context for each attribute
- Reduces hallucination by focusing on relevant information
- Arm-specific context prevents cross-contamination

### 2. Enhanced Completeness
- Treatment arm separation ensures comprehensive coverage
- No missed treatment variations or dose differences
- Systematic approach to complex trial designs

### 3. Better Quality Control
- Multi-stage validation process
- Confidence scoring at multiple levels
- Quality assessment and feedback loops

### 4. Scalability
- Batch processing per abstract
- Parallel processing of treatment arms
- Efficient RAG context retrieval

### 5. Maintainability
- Clean separation of concerns
- Modular component design
- Easy to extend and modify

## Future Enhancements

### 1. Advanced Treatment Arm Detection
- Machine learning models for arm classification
- Historical data for improved accuracy
- Multi-language support

### 2. Enhanced RAG Strategies
- Hybrid retrieval (dense + sparse)
- Query expansion techniques
- Context ranking improvements

### 3. Quality Improvement
- Active learning for prompt optimization
- Feedback loops for continuous improvement
- Automated quality assessment

### 4. Integration Features
- Real-time processing capabilities
- API endpoints for external access
- Batch processing workflows

This RAG-enhanced extraction workflow provides a robust, scalable solution for clinical trial data extraction that combines the best of both treatment arm separation and targeted attribute extraction approaches.
