#!/usr/bin/env python3
"""Test RAG retrieval directly for NUMBER_OF_PATIENTS."""

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from src.domain.extraction_models import AttributeType
from src.domain.models import (
    ChunkingConfiguration,
    ChunkWithEmbedding,
    EmbeddingConfiguration,
)
from src.infrastructure.arm_aware_rag_provider import ArmAwareRAGContextProvider
from src.infrastructure.langchain.chunking import LangChainChunkingService
from src.infrastructure.langchain.embeddings import LangChainEmbeddingService
from src.infrastructure.langchain.vector_store import LangChainVectorStore
from src.infrastructure.rag_config_loader import RAGConfigLoader

os.environ["TOKENIZERS_PARALLELISM"] = "false"
load_dotenv()

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


async def test_rag_retrieval():
    """Test RAG retrieval for NUMBER_OF_PATIENTS."""
    
    embedding_service = LangChainEmbeddingService()
    vector_store_service = LangChainVectorStore(
        embedding_service=embedding_service,
        collection_name="test_rag_retrieval",
    )
    
    chunking_config = ChunkingConfiguration(
        max_chunk_size=1000,
        chunk_overlap=200,
        preserve_tables=True,
        include_headers=True,
    )
    chunking_service = LangChainChunkingService(chunking_config)
    embedding_config = EmbeddingConfiguration()
    
    arm_aware_rag_provider = ArmAwareRAGContextProvider(
        vector_store=vector_store_service,
        embedding_service=embedding_service,
    )
    
    # Load queries
    config_loader = RAGConfigLoader()
    queries = config_loader.get_query_templates(AttributeType.NUMBER_OF_PATIENTS)
    print(f"Loaded {len(queries)} queries for NUMBER_OF_PATIENTS")
    print(f"First 5 queries: {queries[:5]}")
    
    # Test abstracts
    test_cases = {
        "10003": {"expected": "60", "pattern": "(n=60)"},
        "10009": {"expected": "64", "pattern": "64 patients"},
    }
    
    abstract_path = Path("data/postprocessed/ASCO_Abstracts/ASCO_2020.md")
    with open(abstract_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    for abstract_id, test_info in test_cases.items():
        print(f"\n{'='*80}")
        print(f"TESTING ABSTRACT {abstract_id}")
        print(f"{'='*80}")
        
        # Extract and index abstract
        abstract_start = content.find(f"### Abstract ID: {abstract_id}")
        if abstract_start == -1:
            continue
        
        abstract_end = content.find("---", abstract_start + 1)
        if abstract_end == -1:
            abstract_end = len(content)
        abstract_text = content[abstract_start:abstract_end].strip()
        
        # Index
        chunks = await chunking_service.chunk_content(
            content=abstract_text,
            configuration=chunking_config,
            document_id=abstract_id,
            filename=str(abstract_path),
        )
        
        chunks_with_embeddings = []
        for chunk in chunks:
            embedding = await embedding_service.generate_embedding(
                chunk.content, embedding_config
            )
            chunk_with_embedding = ChunkWithEmbedding(
                id=chunk.id,
                document_id=chunk.document_id,
                content=chunk.content,
                chunk_type=chunk.chunk_type,
                metadata=chunk.metadata,
                sequence_number=chunk.sequence_number,
                token_count=chunk.token_count,
                embedding=embedding,
            )
            chunks_with_embeddings.append(chunk_with_embedding)
        
        await vector_store_service.upsert_chunks(chunks_with_embeddings)
        
        # Find Methods chunk
        methods_chunk = None
        for chunk in chunks:
            if chunk.chunk_type.value == "methods":
                methods_chunk = chunk
                break
        
        if methods_chunk:
            has_pattern = test_info['pattern'].lower() in methods_chunk.content.lower()
            print(f"Methods chunk: {len(methods_chunk.content)} chars, has_pattern={has_pattern}")
            if has_pattern:
                # Show the line with pattern
                for line in methods_chunk.content.split('\n'):
                    if test_info['pattern'].lower() in line.lower():
                        print(f"  Pattern found in: {line[:200]}")
        
        # Test RAG retrieval - also check chunk types
        print(f"\nTesting RAG retrieval...")
        
        # First, let's manually search to see what chunk types we get
        from src.infrastructure.langchain.vector_store import SearchQuery
        from src.domain.rag_optimization_config import RAGOptimizationConfig
        
        required_chunk_types = RAGOptimizationConfig.get_required_chunk_types(
            AttributeType.NUMBER_OF_PATIENTS
        )
        print(f"Required chunk types: {required_chunk_types}")
        
        # Test a Methods-specific query
        test_query = SearchQuery(
            text="study design enrolled patients",
            top_k=5,
            similarity_threshold=0.1,
            metadata_filters={
                "document_id": abstract_id,
                "chunk_type": required_chunk_types,
            },
        )
        
        search_results = await vector_store_service.search(test_query)
        print(f"\nDirect search with Methods query: {len(search_results)} results")
        for i, result in enumerate(search_results[:3], 1):
            chunk_type = result.chunk.chunk_type.value if hasattr(result.chunk, 'chunk_type') else 'unknown'
            content = result.chunk.content if hasattr(result.chunk, 'content') else str(result.chunk)
            has_pattern = test_info['pattern'].lower() in content.lower()
            marker = "✓" if has_pattern else " "
            print(f"  {marker} Result {i}: type={chunk_type}, len={len(content)}, has_pattern={has_pattern}")
            if has_pattern:
                for line in content.split('\n'):
                    if test_info['pattern'].lower() in line.lower():
                        print(f"      Found: {line[:200]}")
        
        # Now test the actual RAG retrieval
        context_texts = await arm_aware_rag_provider.get_context_for_attribute(
            document_id=abstract_id,
            attribute_type=AttributeType.NUMBER_OF_PATIENTS,
            context_chunks=10,
            similarity_threshold=0.1,
        )
        
        print(f"\nRAG retrieval: {len(context_texts)} chunks")
        
        if context_texts:
            for i, text in enumerate(context_texts[:3], 1):
                has_pattern = test_info['pattern'].lower() in text.lower()
                marker = "✓" if has_pattern else " "
                print(f"  {marker} Chunk {i}: {len(text)} chars, has_pattern={has_pattern}")
                if has_pattern:
                    for line in text.split('\n'):
                        if test_info['pattern'].lower() in line.lower():
                            print(f"      Found: {line[:200]}")
                else:
                    preview = text[:150].replace('\n', ' ')
                    print(f"      Preview: {preview}...")
        else:
            print(f"  ❌ No chunks retrieved!")


if __name__ == "__main__":
    asyncio.run(test_rag_retrieval())

