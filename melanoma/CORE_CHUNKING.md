# Core Chunking Module

## Overview

The core chunking module provides intelligent text chunking specifically designed for oncology abstracts. It follows clean architecture principles with domain-driven design, making it easy to test, maintain, and extend.

## Features

### 🎯 **Semantic Chunking Strategies**
- **Header-Based**: Chunks by markdown structure (### Abstract ID, #### Sections)
- **Recursive**: Splits large content with configurable overlap
- **Hybrid**: Combines both approaches for optimal results

### 📊 **Rich Metadata Extraction**
- **Abstract IDs**: ASCO numeric (10000) and ESMO alphanumeric (1076O) formats  
- **Years**: Extracted from filename patterns (ASCO_2020.md, ESMO_2020.md)
- **Clinical Trials**: NCT number detection across all formats
- **Sponsors**: Multi-pattern recognition for different conference fields
  - ASCO: "Research Sponsor"
  - ESMO: "Legal entity responsible for the study", "Funding"
- **Table detection**: Automatic identification and preservation

### 🧪 **Content-Aware Processing**
- **Conference Support**: ASCO and ESMO formats with structure-specific parsing
- **Section Recognition**: 
  - Common: Background, Methods, Results, Conclusions
  - ESMO-specific: Trial Design sections
- **Semantic Boundaries**: Preserves logical content flow
- **Table Handling**: Separate chunks with content-aware splitting
- **Configurable Parameters**: Chunk sizes, overlap, preservation options

## Architecture

```
src/
├── domain/
│   ├── models.py          # Core entities (Chunk, ChunkingConfiguration)
│   └── interfaces.py      # Abstract interfaces
└── infrastructure/
    └── chunking_strategies.py  # Strategy implementations
```

### Domain Models

#### `Chunk`
```python
class Chunk(BaseModel):
    id: UUID
    document_id: UUID
    content: str
    chunk_type: ChunkType  # BACKGROUND, METHODS, RESULTS, etc.
    metadata: dict[str, Any]
    sequence_number: int
    token_count: Optional[int]
    created_at: datetime
```

#### `ChunkingConfiguration`
```python
class ChunkingConfiguration(BaseModel):
    strategy: ChunkingStrategy
    max_chunk_size: int = 1000
    chunk_overlap: int = 200
    preserve_tables: bool = True
    include_headers: bool = True
```

### Chunking Strategies

#### 1. Header-Based Strategy
Best for well-structured abstracts with clear section headers.

```python
strategy = ChunkingStrategyFactory.create_strategy(ChunkingStrategy.HEADER_BASED)
chunks = await strategy.chunk_content(content, config, document_id, filename)
```

**Produces chunks like:**
- Abstract header chunk
- Background section chunk
- Methods section chunk
- Results section chunk (+ separate table chunks if present)
- Conclusions section chunk

#### 2. Recursive Strategy
Ideal for large content that needs size-based splitting.

```python
config = ChunkingConfiguration(
    strategy=ChunkingStrategy.RECURSIVE,
    max_chunk_size=800,
    chunk_overlap=150
)
```

#### 3. Hybrid Strategy (Recommended)
Combines header-based and recursive approaches.

```python
config = ChunkingConfiguration(
    strategy=ChunkingStrategy.HYBRID,
    max_chunk_size=1000,
    chunk_overlap=200,
    preserve_tables=True
)
```

## Quick Start

### Basic Usage

```python
import asyncio
from uuid import uuid4
from src.domain.models import ChunkingConfiguration, ChunkingStrategy
from src.infrastructure.chunking_strategies import ChunkingStrategyFactory

async def chunk_abstract():
    # Create strategy
    strategy = ChunkingStrategyFactory.create_strategy(ChunkingStrategy.HYBRID)
    
    # Configure chunking
    config = ChunkingConfiguration(
        strategy=ChunkingStrategy.HYBRID,
        max_chunk_size=800,
        chunk_overlap=150,
        preserve_tables=True
    )
    
    # Process content
    chunks = await strategy.chunk_content(
        content=abstract_text,
        configuration=config,
        document_id=str(uuid4()),
        filename="ASCO_2024.md"
    )
    
    # Analyze results
    for chunk in chunks:
        print(f"Type: {chunk.chunk_type.value}")
        print(f"Length: {len(chunk.content)}")
        print(f"Metadata: {chunk.metadata}")
        print("---")

asyncio.run(chunk_abstract())
```

### Running the Demo

```bash
# Core functionality demonstration
poetry run python chunking_demo.py

# Process real oncology abstract data
poetry run python chunk_abstracts.py --max-abstracts 5

# Process ESMO data
poetry run python chunk_abstracts.py --file ESMO_2020.md --max-abstracts 5

# Try different strategies and configurations
poetry run python chunk_abstracts.py --strategy header_based --chunk-size 1200
poetry run python chunk_abstracts.py --file ASCO_2021.md --strategy recursive
poetry run python chunk_abstracts.py --file ESMO_2021.md --strategy hybrid
```

**Demo Output:**
```
=== Header-Based Chunking Results ===
Total chunks: 5
Average chunk length: 425 characters
Chunk type distribution: {'abstract_header': 1, 'background': 1, 'methods': 1, 'results': 1, 'conclusions': 1}

Sample chunk (Type: background):
Content: We conducted the phase 3 double-blind EORTC 1325/KEYNOTE-054 trial...
Metadata: {'abstract_id': '10000', 'clinical_trial_id': 'NCT02362594', 'sponsor': 'Merck'}
```

## Metadata Extraction

The system automatically extracts rich metadata from abstracts:

```python
# From content
metadata = {
    'abstract_id': '10000',           # ### Abstract ID: 10000
    'clinical_trial_id': 'NCT02362594', # **Clinical trial information:** NCT02362594
    'sponsor': 'Merck',               # **Research Sponsor:** Merck
    'has_table': True,                # Detected table content
    'title': 'Pembrolizumab versus...' # **Title:** ...
}

# From filename
metadata['year'] = 2024  # From "ASCO_2024.md"
```

## Configuration Options

### Chunk Size Management
```python
config = ChunkingConfiguration(
    max_chunk_size=1000,    # Maximum characters per chunk
    chunk_overlap=200,      # Overlap between chunks for context
)
```

### Table Handling
```python
config = ChunkingConfiguration(
    preserve_tables=True,   # Keep tables as separate chunks
    include_headers=True,   # Include section headers in chunks
)
```

### Strategy Selection
```python
# For well-structured abstracts
strategy = ChunkingStrategy.HEADER_BASED

# For large content needing splitting
strategy = ChunkingStrategy.RECURSIVE

# Best of both (recommended)
strategy = ChunkingStrategy.HYBRID
```

## Testing

### Running Tests
```bash
# Run all chunking tests
pytest tests/test_chunking_strategies.py

# Run with verbose output
pytest tests/test_chunking_strategies.py -v

# Run specific test
pytest tests/test_chunking_strategies.py::TestHeaderBasedChunkingStrategy::test_chunk_content
```

### Test Coverage
- ✅ Header-based chunking with real abstract content
- ✅ Recursive chunking with size constraints
- ✅ Hybrid strategy combining both approaches
- ✅ Metadata extraction from various formats
- ✅ Table detection and preservation
- ✅ Configuration validation
- ✅ Error handling and edge cases

## Extension Points

### Adding New Strategies

1. Implement the interface:
```python
class CustomChunkingStrategy(ChunkingStrategyInterface):
    async def chunk_content(self, content, configuration, document_id=None, filename=""):
        # Your custom logic here
        return chunks
    
    def supports_configuration(self, configuration):
        return configuration.strategy == ChunkingStrategy.CUSTOM
```

2. Register in factory:
```python
class ChunkingStrategyFactory:
    _strategies = {
        ChunkingStrategy.HEADER_BASED: HeaderBasedChunkingStrategy,
        ChunkingStrategy.RECURSIVE: RecursiveChunkingStrategy,
        ChunkingStrategy.HYBRID: HybridChunkingStrategy,
        ChunkingStrategy.CUSTOM: CustomChunkingStrategy,  # Add here
    }
```

### Custom Metadata Extractors

```python
def _extract_custom_metadata(self, content: str) -> Dict[str, Any]:
    metadata = {}
    
    # Extract custom patterns
    custom_match = re.search(r'Custom Pattern: (.+)', content)
    if custom_match:
        metadata['custom_field'] = custom_match.group(1)
    
    return metadata
```

## Performance Considerations

### For Large Documents
- Use `ChunkingStrategy.RECURSIVE` with appropriate chunk sizes
- Consider processing in batches
- Monitor memory usage for very large abstracts

### For Many Small Documents
- Use `ChunkingStrategy.HEADER_BASED` for faster processing
- Batch multiple abstracts together
- Cache strategy instances

## Best Practices

### 1. Strategy Selection
- **Header-Based**: Well-structured abstracts with clear sections
- **Recursive**: Large abstracts or documents without clear structure
- **Hybrid**: Most abstracts (recommended default)

### 2. Configuration Tuning
```python
# For shorter abstracts
config = ChunkingConfiguration(max_chunk_size=600, chunk_overlap=100)

# For longer abstracts
config = ChunkingConfiguration(max_chunk_size=1200, chunk_overlap=300)

# For table-heavy content
config = ChunkingConfiguration(preserve_tables=True, include_headers=True)
```

### 3. Error Handling
```python
try:
    chunks = await strategy.chunk_content(content, config)
except Exception as e:
    logger.error(f"Chunking failed: {str(e)}")
    # Fallback to simpler strategy
    strategy = ChunkingStrategyFactory.create_strategy(ChunkingStrategy.RECURSIVE)
    chunks = await strategy.chunk_content(content, config)
```

## Future Enhancements

This core module is designed to be extended with:

1. **Embedding Integration**: Add vector embeddings to chunks
2. **Vector Storage**: Store chunks in vector databases (ChromaDB, FAISS)
3. **Advanced Metadata**: Extract more complex patterns
4. **Semantic Chunking**: Use AI models for intelligent boundaries
5. **Multi-format Support**: Handle PDFs, Word docs, etc.

## Contributing

1. Follow the existing patterns and interfaces
2. Add tests for new functionality
3. Update documentation
4. Ensure clean architecture separation
5. Run the full test suite before submitting

## Examples

### Processing ASCO Abstracts
```python
# Read abstract file
with open("data/processed/ASCO_2024.md", "r") as f:
    content = f.read()

# Process each abstract separately
abstracts = content.split("### Abstract ID:")
for i, abstract_content in enumerate(abstracts[1:]):  # Skip first empty split
    abstract_content = "### Abstract ID:" + abstract_content
    
    chunks = await strategy.chunk_content(
        content=abstract_content,
        configuration=config,
        document_id=f"asco_2024_{i}",
        filename="ASCO_2024.md"
    )
    
    print(f"Abstract {i}: {len(chunks)} chunks")
```

This core chunking module provides a solid foundation for RAG applications with oncology abstracts, focusing on semantic understanding and clean, maintainable code.
