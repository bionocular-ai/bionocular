#!/usr/bin/env python3
"""Test chunk retrieval for NUMBER_OF_PATIENTS to verify prioritization logic."""

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
from src.domain.rag_optimization_config import RAGOptimizationConfig

os.environ["TOKENIZERS_PARALLELISM"] = "false"
load_dotenv()

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_chunk_retrieval():
    """Test chunk retrieval for NUMBER_OF_PATIENTS to verify prioritization."""
    
    embedding_service = LangChainEmbeddingService()
    vector_store_service = LangChainVectorStore(
        embedding_service=embedding_service,
        collection_name="test_number_of_patients",
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
    
    # Test abstract 10009 specifically
    test_abstracts = {
        "10009": {"expected": "64", "pattern": "64 patients"},
    }
    
    abstract_path = Path("data/postprocessed/ASCO_Abstracts/ASCO_2020.md")
    if not abstract_path.exists():
        logger.error(f"Abstract file not found: {abstract_path}")
        return
    
    with open(abstract_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    print("\n" + "=" * 80)
    print("NUMBER_OF_PATIENTS CHUNK RETRIEVAL TEST")
    print("=" * 80)
    print("Priority order: Methods > Table > Results (Conclusions excluded)")
    print("=" * 80)
    
    for abstract_id, test_info in test_abstracts.items():
        expected_value = test_info["expected"]
        pattern = test_info["pattern"]
        
        print(f"\n{'='*80}")
        print(f"TESTING ABSTRACT {abstract_id}")
        print(f"{'='*80}")
        print(f"  Expected value: {expected_value}")
        print(f"  Pattern to find: {pattern}")
        
        # Extract abstract
        abstract_start = content.find(f"### Abstract ID: {abstract_id}")
        if abstract_start == -1:
            print(f"  ❌ Abstract {abstract_id} not found")
            continue
        
        abstract_end = content.find("---", abstract_start + 1)
        if abstract_end == -1:
            abstract_end = len(content)
        abstract_text = content[abstract_start:abstract_end].strip()
        
        # Index abstract
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
        
        # Analyze chunk types
        chunk_types = {}
        methods_chunk = None
        for chunk in chunks:
            chunk_type = chunk.chunk_type.value
            chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
            if chunk_type == "methods":
                methods_chunk = chunk
                if pattern.lower() in chunk.content.lower():
                    print(f"  ✓ Pattern found in Methods chunk")
        
        print(f"  Indexed {len(chunks)} chunks: {dict(chunk_types)}")
        
        # Test chunk retrieval using the updated method
        print(f"\n  Testing RAG retrieval...")
        try:
            # First, let's check what queries are being used
            from src.infrastructure.rag_config_loader import RAGConfigLoader
            rag_config = RAGConfigLoader()
            queries = rag_config.get_query_templates(AttributeType.NUMBER_OF_PATIENTS)
            print(f"  Using {len(queries)} queries for NUMBER_OF_PATIENTS")
            print(f"  First 3 queries: {queries[:3]}")
            
            # Also test direct search to see what chunks exist
            from src.infrastructure.langchain.vector_store import SearchQuery
            from src.domain.rag_optimization_config import RAGOptimizationConfig
            required_chunk_types = RAGOptimizationConfig.get_required_chunk_types(
                AttributeType.NUMBER_OF_PATIENTS
            )
            print(f"  Required chunk types: {required_chunk_types}")
            
            # Direct search with Methods query
            test_query = SearchQuery(
                text="tumor biopsies from number patients",
                top_k=5,
                similarity_threshold=0.1,
                metadata_filters={
                    "document_id": abstract_id,
                    "chunk_type": required_chunk_types,
                },
            )
            direct_results = await vector_store_service.search(test_query)
            print(f"\n  Direct search with Methods query: {len(direct_results)} results")
            for i, result in enumerate(direct_results[:3], 1):
                chunk_type = result.chunk.chunk_type.value if hasattr(result.chunk, 'chunk_type') else 'unknown'
                content = result.chunk.content if hasattr(result.chunk, 'content') else str(result.chunk)
                has_pattern = pattern.lower() in content.lower()
                marker = "✓" if has_pattern else " "
                print(f"    {marker} Result {i}: type={chunk_type}, len={len(content)}, has_pattern={has_pattern}")
                if has_pattern:
                    for line in content.split('\n'):
                        if pattern.lower() in line.lower():
                            print(f"      Found: {line[:200]}")
            
            # Check if Methods chunk would pass keyword filter
            if methods_chunk:
                from src.domain.rag_optimization_config import RAGOptimizationConfig
                should_include = RAGOptimizationConfig.should_include_chunk(
                    methods_chunk.content, AttributeType.NUMBER_OF_PATIENTS
                )
                print(f"  Methods chunk passes keyword filter: {'✓' if should_include else '❌'}")
                if not should_include:
                    print(f"    Methods chunk content preview: {methods_chunk.content[:200]}...")
            
            context_texts = await arm_aware_rag_provider.get_context_for_attribute(
                document_id=abstract_id,
                attribute_type=AttributeType.NUMBER_OF_PATIENTS,
                context_chunks=10,
                similarity_threshold=0.1,
            )
            
            if context_texts:
                print(f"  ✓ Retrieved {len(context_texts)} chunks")
                
                # Check prioritization order and pattern presence
                found_pattern = False
                methods_found = False
                priority_order = []
                
                for i, text in enumerate(context_texts[:5], 1):
                    # Try to determine chunk type from content (check if it's Methods-like)
                    is_methods = any(keyword in text.lower()[:100] for keyword in [
                        "methods", "study design", "enrolled", "trial", "phase"
                    ])
                    is_table = "|" in text or "\t" in text
                    is_results = any(keyword in text.lower()[:100] for keyword in [
                        "results", "response", "efficacy", "outcome"
                    ])
                    
                    if is_methods:
                        chunk_type_label = "methods"
                        methods_found = True
                    elif is_table:
                        chunk_type_label = "table"
                    elif is_results:
                        chunk_type_label = "results"
                    else:
                        chunk_type_label = "other"
                    
                    priority_order.append(chunk_type_label)
                    
                    has_pattern = pattern.lower() in text.lower()
                    if has_pattern:
                        found_pattern = True
                        marker = "✓"
                    else:
                        marker = " "
                    
                    preview = text[:150].replace('\n', ' ')
                    print(f"    {marker} Chunk {i} [{chunk_type_label}]: {len(text)} chars")
                    if has_pattern:
                        # Show the line with pattern
                        for line in text.split('\n'):
                            if pattern.lower() in line.lower():
                                print(f"      Found: {line[:200]}")
                    else:
                        print(f"      Preview: {preview}...")
                
                # Summary
                print(f"\n  Summary:")
                print(f"    Pattern found: {'✓' if found_pattern else '❌'}")
                print(f"    Methods chunk retrieved: {'✓' if methods_found else '❌'}")
                print(f"    Priority order: {' > '.join(priority_order[:3])}")
                
                # Check if Methods is prioritized
                if priority_order and priority_order[0] == "methods":
                    print(f"    ✓ Methods chunk is first (correct prioritization)")
                elif methods_found:
                    methods_pos = next((i for i, ct in enumerate(priority_order) if ct == "methods"), -1)
                    if methods_pos > 0:
                        print(f"    ⚠️  Methods chunk at position {methods_pos + 1} (should be first)")
                else:
                    print(f"    ❌ Methods chunk not retrieved")
            else:
                print(f"  ❌ No chunks retrieved")
        except Exception as e:
            print(f"  ⚠️  Chunk retrieval failed: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_chunk_retrieval())

