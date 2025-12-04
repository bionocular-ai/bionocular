"""Test script for improved publication chunking with Efficacy prioritization."""

import asyncio
from pathlib import Path

from src.domain.models import ChunkingConfiguration, ChunkingStrategy
from src.infrastructure.langchain.chunking import LangChainChunkingService


async def test_publication_chunking():
    """Test the improved publication chunking on sample publications."""

    test_files = [
        "data/postprocessed/Publications/Batch-I_3.md",
        "data/postprocessed/Publications/Batch-I_4.md",
        "data/postprocessed/Publications/Batch-I_6.md",
        "data/postprocessed/Publications/Batch-I_7.md",
        "data/postprocessed/Publications/Batch-I_8.md",
        "data/postprocessed/Publications/Batch-I_9.md",
    ]

    config = ChunkingConfiguration(strategy=ChunkingStrategy.HYBRID)
    chunking_service = LangChainChunkingService(config)

    for file_path in test_files:
        publication_path = Path(file_path)
        if not publication_path.exists():
            print(f"⚠️  File not found: {publication_path}")
            continue

        content = publication_path.read_text(encoding="utf-8")
        print(f"\n{'='*80}")
        print(f"📄 Testing: {publication_path.name}")
        print(f"{'='*80}")
        print(f"Content length: {len(content):,} characters\n")

        # Chunk the publication
        chunks = await chunking_service.chunk_content(
            content=content,
            configuration=config,
            filename=str(publication_path),
        )

        # Analyze chunks
        results_chunks = [c for c in chunks if c.chunk_type.value == "results"]
        efficacy_chunks = [
            c
            for c in chunks
            if c.chunk_type.value == "results"
            and c.metadata.get("is_efficacy_subsection", False)
        ]
        table_chunks = [c for c in chunks if c.chunk_type.value == "table"]

        print("📊 Chunk Analysis:")
        print(f"  - Total chunks: {len(chunks)}")
        print(f"  - Results chunks: {len(results_chunks)}")
        print(f"  - Efficacy/Major Results chunks: {len(efficacy_chunks)}")
        print(f"  - Table chunks: {len(table_chunks)}")
        print(
            f"  - Other chunks: {len(chunks) - len(results_chunks) - len(table_chunks)}"
        )

        # Show Efficacy chunks
        if efficacy_chunks:
            print(f"\n🎯 Efficacy/Major Results Chunks ({len(efficacy_chunks)}):")
            for i, chunk in enumerate(efficacy_chunks[:3], 1):  # Show first 3
                is_subchunk = chunk.metadata.get("is_subchunk", False)
                subchunk_info = (
                    f" (subchunk {chunk.metadata.get('subchunk_index', '?')}/{chunk.metadata.get('total_subchunks', '?')})"
                    if is_subchunk
                    else ""
                )
                print(f"  {i}. Length: {len(chunk.content)} chars{subchunk_info}")
                preview = chunk.content[:120].replace("\n", " ")
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

        # Show chunk type distribution
        chunk_types = {}
        for chunk in chunks:
            chunk_type = chunk.chunk_type.value
            chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1

        print("\n📑 Chunk Types Distribution:")
        for chunk_type, count in sorted(chunk_types.items()):
            print(f"  - {chunk_type}: {count}")


if __name__ == "__main__":
    asyncio.run(test_publication_chunking())
