# RAG-Enhanced Clinical Trial Extraction Workflow

## Overview

This document outlines the workflow design for integrating RAG (Retrieval-Augmented Generation) with clinical trial extraction, combining treatment arm separation with targeted attribute extraction to improve quality and reduce hallucination.

## Workflow Architecture

### Phase 1: Document Processing & Treatment Arm Separation

```
Abstract Input
    ↓
[Document Preprocessing]
    ↓
[Treatment Arm Separation LLM]
    ↓
Treatment Arms Identified
    ↓
[Arm-Specific Context Preparation]
```

### Phase 2: RAG-Enhanced Attribute Extraction

```
For Each Treatment Arm:
    ↓
[RAG Context Retrieval] → [Attribute-Specific Context]
    ↓
[Targeted LLM Extraction] → [Validation & Confidence Scoring]
    ↓
[Persistence to Database]
```

## Detailed Workflow Steps

### Step 1: Document Ingestion & Preprocessing

**Input**: Clinical trial abstract (PDF, text, or structured data)

**Process**:
1. **Document Parsing**: Extract text content and metadata
2. **Abstract Validation**: Check for clinical content, NCT numbers, etc.
3. **Chunking**: Split document into semantic chunks for RAG
4. **Embedding Generation**: Create vector embeddings for chunks
5. **Vector Storage**: Store chunks in vector database

**Output**: Processed document with indexed chunks

### Step 2: Treatment Arm Separation

**Input**: Full abstract text

**Process**:
1. **Treatment Arm Detection**: Use LLM with full context to identify treatment arms
2. **Arm Classification**: Categorize arms (monotherapy, combination, dose variations)
3. **Arm Metadata Extraction**: Extract arm-specific information (drug names, doses, patient counts)
4. **Arm Validation**: Validate arm separation quality

**LLM Prompt Strategy**:
```python
TREATMENT_ARM_SEPARATION_PROMPT = """
TASK: Identify and separate treatment arms from this clinical trial abstract.

CRITICAL REQUIREMENTS:
1. Each unique treatment regimen is a separate arm
2. Different doses of the same drug are separate arms
3. Combination therapies are single arms with "+" notation
4. Extract arm-specific metadata (drug names, doses, patient counts)

OUTPUT FORMAT:
{
  "treatment_arms": [
    {
      "arm_id": "arm_1",
      "arm_name": "Nivolumab 3mg/kg",
      "generic_name": "Nivolumab",
      "dose": "3mg/kg",
      "patient_count": 313,
      "line_of_treatment": "First Line",
      "arm_type": "monotherapy"
    }
  ]
}
"""
```

**Output**: List of treatment arms with metadata

### Step 3: RAG Context Retrieval (Per Treatment Arm)

**Input**: Treatment arm + abstract ID

**Process**:
1. **Attribute-Specific Queries**: Generate queries for each attribute type
2. **Vector Search**: Retrieve relevant chunks using similarity search
3. **Context Assembly**: Combine chunks with arm-specific context
4. **Context Ranking**: Rank chunks by relevance and similarity

**RAG Query Strategy**:
```python
# For each attribute type, generate targeted queries
ATTRIBUTE_QUERIES = {
    AttributeType.NCT_NUMBER: [
        "NCT number clinical trial identifier",
        "ClinicalTrials.gov registration number"
    ],
    AttributeType.GENERIC_NAME: [
        "generic drug name treatment arm",
        "medication name therapy"
    ],
    AttributeType.P_VALUE_OS: [
        "overall survival p-value significance",
        "OS p-value statistical significance"
    ],
    AttributeType.OBJECTIVE_RESPONSE_RATE: [
        "objective response rate ORR",
        "response rate efficacy"
    ],
    AttributeType.GRADE_3_PLUS_AE: [
        "grade 3 adverse events toxicity",
        "grade 3+ adverse events"
    ]
}
```

**Output**: Arm-specific context chunks for each attribute

### Step 4: Targeted Attribute Extraction (Per Arm)

**Input**: Treatment arm + RAG context + attribute type

**Process**:
1. **Context Assembly**: Combine arm metadata with RAG context
2. **Attribute-Specific Prompting**: Use specialized prompts for each attribute
3. **LLM Extraction**: Extract attribute value with confidence scoring
4. **Validation**: Validate extracted values against expected formats
5. **Confidence Calculation**: Calculate extraction confidence

**Enhanced Prompt Strategy**:
```python
def create_arm_specific_prompt(arm: TreatmentArm, attribute_type: AttributeType, context: List[str]) -> str:
    return f"""
TASK: Extract {attribute_type.value} for treatment arm: {arm.arm_name}

TREATMENT ARM CONTEXT:
- Arm Name: {arm.arm_name}
- Generic Name: {arm.generic_name}
- Dose: {arm.dose}
- Patient Count: {arm.patient_count}
- Line of Treatment: {arm.line_of_treatment}

RAG CONTEXT:
{format_context_chunks(context)}

EXTRACTION INSTRUCTIONS:
{get_attribute_specific_instructions(attribute_type)}

OUTPUT: Extract only the {attribute_type.value} value for this specific treatment arm.
"""
```

**Output**: Extracted attribute with confidence score

### Step 5: Validation & Quality Assessment

**Input**: Extracted attributes per treatment arm

**Process**:
1. **Format Validation**: Validate attribute formats (NCT format, percentage ranges, etc.)
2. **Cross-Arm Validation**: Check for consistency across arms
3. **Confidence Assessment**: Evaluate extraction confidence
4. **Quality Scoring**: Calculate overall extraction quality

**Validation Rules**:
```python
VALIDATION_RULES = {
    AttributeType.NCT_NUMBER: {
        "pattern": r"NCT\d{8}",
        "required": True,
        "cross_arm_consistency": True
    },
    AttributeType.OBJECTIVE_RESPONSE_RATE: {
        "range": [0, 100],
        "format": "percentage",
        "required": False
    },
    AttributeType.P_VALUE_OS: {
        "range": [0, 1],
        "format": "numeric_or_categorical",
        "required": False
    }
}
```

**Output**: Validated attributes with quality scores

### Step 6: Persistence & Storage

**Input**: Validated attributes per treatment arm

**Process**:
1. **Database Storage**: Store extraction results in database
2. **Vector Indexing**: Update vector store with extraction metadata
3. **Audit Trail**: Log extraction process and results
4. **Quality Metrics**: Store quality assessment results

**Database Schema**:
```sql
-- Treatment Arms Table
CREATE TABLE treatment_arms (
    id UUID PRIMARY KEY,
    abstract_id UUID NOT NULL,
    arm_name VARCHAR(255) NOT NULL,
    generic_name VARCHAR(255),
    dose VARCHAR(100),
    patient_count INTEGER,
    line_of_treatment VARCHAR(50),
    arm_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Extracted Attributes Table
CREATE TABLE extracted_attributes (
    id UUID PRIMARY KEY,
    treatment_arm_id UUID REFERENCES treatment_arms(id),
    attribute_type VARCHAR(50) NOT NULL,
    value TEXT,
    confidence_score DECIMAL(3,2),
    validation_status VARCHAR(20),
    source_chunks TEXT[],
    extracted_at TIMESTAMP DEFAULT NOW()
);
```

**Output**: Persisted extraction results

## Implementation Components

### 1. Treatment Arm Separator Service

```python
class TreatmentArmSeparator:
    async def separate_arms(self, abstract_text: str) -> List[TreatmentArm]:
        """Separate treatment arms from abstract text."""
        pass
    
    async def validate_arm_separation(self, arms: List[TreatmentArm]) -> ValidationResult:
        """Validate treatment arm separation quality."""
        pass
```

### 2. RAG-Enhanced Context Provider

```python
class ArmAwareRAGContextProvider:
    async def get_context_for_arm_attribute(
        self, 
        arm: TreatmentArm, 
        attribute_type: AttributeType
    ) -> List[SearchResult]:
        """Get RAG context for specific arm and attribute."""
        pass
```

### 3. Arm-Specific Attribute Extractor

```python
class ArmSpecificAttributeExtractor:
    async def extract_attributes_for_arm(
        self, 
        arm: TreatmentArm, 
        context: List[SearchResult]
    ) -> Dict[AttributeType, ExtractedAttribute]:
        """Extract all attributes for a specific treatment arm."""
        pass
```

### 4. Quality Assessment Service

```python
class ExtractionQualityAssessor:
    async def assess_extraction_quality(
        self, 
        extraction_results: Dict[str, Any]
    ) -> QualityAssessment:
        """Assess overall extraction quality."""
        pass
```

## Workflow Benefits

### 1. **Improved Precision**
- RAG provides targeted context for each attribute
- Reduces hallucination by focusing on relevant information
- Arm-specific context prevents cross-contamination

### 2. **Enhanced Completeness**
- Treatment arm separation ensures comprehensive coverage
- No missed treatment variations or dose differences
- Systematic approach to complex trial designs

### 3. **Better Quality Control**
- Multi-stage validation process
- Confidence scoring at multiple levels
- Quality assessment and feedback loops

### 4. **Scalability**
- Batch processing per abstract
- Parallel processing of treatment arms
- Efficient RAG context retrieval

### 5. **Maintainability**
- Clean separation of concerns
- Modular component design
- Easy to extend and modify

## Error Handling & Recovery

### 1. **Treatment Arm Separation Failures**
- Fallback to single-arm processing
- Manual review triggers
- Quality alerts for low-confidence separations

### 2. **RAG Context Retrieval Failures**
- Fallback to full abstract context
- Alternative query strategies
- Context quality assessment

### 3. **Attribute Extraction Failures**
- Retry with different prompts
- Manual extraction triggers
- Quality-based re-extraction

### 4. **Validation Failures**
- Cross-validation with multiple sources
- Manual review workflows
- Confidence-based filtering

## Performance Considerations

### 1. **Parallel Processing**
- Process treatment arms in parallel
- Batch RAG context retrieval
- Concurrent attribute extraction

### 2. **Caching Strategy**
- Cache RAG context for similar queries
- Reuse treatment arm separations
- Store intermediate results

### 3. **Resource Management**
- LLM rate limiting
- Vector database optimization
- Memory management for large documents

## Monitoring & Metrics

### 1. **Extraction Quality Metrics**
- Attribute extraction success rate
- Confidence score distribution
- Validation failure rates

### 2. **Performance Metrics**
- Processing time per abstract
- RAG context retrieval time
- LLM response times

### 3. **Quality Trends**
- Quality score trends over time
- Common extraction failures
- Improvement opportunities

This workflow design provides a comprehensive, scalable approach to RAG-enhanced clinical trial extraction that combines the best of both the current and legacy approaches while maintaining high quality and reducing hallucination.
