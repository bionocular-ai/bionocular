"""Test script for publication-specific chunking strategy."""

import asyncio
from pathlib import Path

from src.domain.models import ChunkingConfiguration, ChunkingStrategy
from src.infrastructure.langchain.chunking import LangChainChunkingService


async def test_publication_chunking():
    """Test the publication chunking strategy on a sample publication."""
    
    # Load a sample publication
    publication_path = Path("data/postprocessed/Publications/Batch-III_31.md")
    if not publication_path.exists():
        print(f"Publication file not found: {publication_path}")
        return
    
    content = publication_path.read_text(encoding="utf-8")
    print(f"Loaded publication: {publication_path.name}")
    print(f"Content length: {len(content)} characters\n")
    
    # Initialize chunking service
    config = ChunkingConfiguration(strategy=ChunkingStrategy.HYBRID)
    chunking_service = LangChainChunkingService(config)
    
    # Chunk the publication
    print("Chunking publication...")
    chunks = await chunking_service.chunk_content(
        content=content,
        configuration=config,
        filename=str(publication_path),
    )
    
    print(f"\n✅ Created {len(chunks)} chunks\n")
    
    # Analyze chunks
    results_chunks = [c for c in chunks if c.chunk_type.value == "results"]
    table_chunks = [c for c in chunks if c.chunk_type.value == "table"]
    
    print("📊 Chunk Analysis:")
    print(f"  - Total chunks: {len(chunks)}")
    print(f"  - Results chunks: {len(results_chunks)}")
    print(f"  - Table chunks: {len(table_chunks)}")
    print(f"  - Other chunks: {len(chunks) - len(results_chunks) - len(table_chunks)}")
    
    # Show Results chunks
    if results_chunks:
        print(f"\n📈 Results Section Chunks ({len(results_chunks)}):")
        for i, chunk in enumerate(results_chunks[:5], 1):  # Show first 5
            is_subchunk = chunk.metadata.get("is_subchunk", False)
            subchunk_info = f" (subchunk {chunk.metadata.get('subchunk_index', '?')}/{chunk.metadata.get('total_subchunks', '?')})" if is_subchunk else ""
            print(f"  {i}. Length: {len(chunk.content)} chars{subchunk_info}")
            preview = chunk.content[:100].replace("\n", " ")
            print(f"     Preview: {preview}...")
    
    # Show table chunks
    if table_chunks:
        print(f"\n📋 Table Chunks ({len(table_chunks)}):")
        for i, chunk in enumerate(table_chunks, 1):
            table_index = chunk.metadata.get("table_index", "?")
            lines = chunk.content.split("\n")
            print(f"  {i}. Table {table_index}: {len(lines)} lines")
            if lines:
                print(f"     First line: {lines[0][:80]}...")
    
    # Show chunk types distribution
    chunk_types = {}
    for chunk in chunks:
        chunk_type = chunk.chunk_type.value
        chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
    
    print(f"\n📑 Chunk Types Distribution:")
    for chunk_type, count in sorted(chunk_types.items()):
        print(f"  - {chunk_type}: {count}")


if __name__ == "__main__":
    asyncio.run(test_publication_chunking())

