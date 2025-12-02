"""Comprehensive retrieval test for ALL numeric attributes across first 10 abstracts.

This script:
1. Indexes first 10 abstracts from ASCO_2020.md
2. Queries each of the 76 numeric attributes
3. Shows retrieval statistics with and without keyword filtering
4. Generates a summary report

Usage:
    python query_all_numeric_attributes.py
    python query_all_numeric_attributes.py --abstracts 5
    python query_all_numeric_attributes.py --output report.json
"""

import argparse
import asyncio
import json
import logging
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from src.app.langchain_factory_service import (
    LangChainServiceFactory,
    ServiceConfiguration,
)
from src.domain.extraction_models import AttributeType
from src.domain.models import (
    ChunkingConfiguration,
    ChunkingStrategy,
    ChunkWithEmbedding,
    EmbeddingConfiguration,
    EmbeddingModel,
    SearchQuery,
    SearchResult,
)
from src.domain.rag_optimization_config import RAGOptimizationConfig
from src.infrastructure.rag_config_loader import RAGConfigLoader

# Configure logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# Keyword mappings for filtering
# Format: List[str] for simple OR matching
#         List[List[str]] for grouped AND matching (all groups must match)
ATTRIBUTE_KEYWORDS = {
    # PFS Family
    AttributeType.MEDIAN_PFS: [
        "pfs",
        "progression-free survival",
        "progression free survival",
    ],
    AttributeType.MEDIAN_FOLLOWUP_PFS: [
        ["pfs", "progression-free", "progression free"],  # Group 1: Must have PFS
        [
            "follow-up",
            "followup",
            "follow up",
            "median follow",
        ],  # Group 2: Must have follow-up (handles "3.05-yr median follow-up")
    ],
    AttributeType.P_VALUE_PFS: [
        ["pfs", "progression-free", "progression free"],  # Group 1: Must have PFS
        ["p-value", "p value", "p"],  # Group 2: Must have p-value
    ],
    AttributeType.HR_PFS: [
        ["pfs", "progression-free", "progression free"],  # Group 1: Must have PFS
        ["hr", "hazard ratio"],  # Group 2: Must have HR
    ],
    AttributeType.PFS_RATE_6M: [
        ["pfs", "progression-free", "progression free"],
        [
            "6 month",
            "6 months",
            "6 mo",
            "6m",
            "6 mth",
            "6 mths",
            "six month",
            "six months",
        ],
    ],
    AttributeType.PFS_RATE_9M: [
        ["pfs", "progression-free", "progression free"],
        [
            "9 month",
            "9 months",
            "9 mo",
            "9m",
            "9 mth",
            "9 mths",
            "nine month",
            "nine months",
        ],
    ],
    AttributeType.PFS_RATE_12M: [
        ["pfs", "progression-free", "progression free"],
        [
            "12 month",
            "12 months",
            "12 mo",
            "12mo",
            "12m",
            "1 year",
            "1 years",
            "1 yr",
            "1yr",
            "1 y",
            "1y",
            "12 mth",
            "12 mths",
            "one year",
            "twelve month",
            "twelve months",
        ],
    ],
    AttributeType.PFS_RATE_18M: [
        ["pfs", "progression-free", "progression free"],
        ["18 month", "18 months", "18 mo", "18mo", "18m", "18 mth", "18 mths"],
    ],
    AttributeType.PFS_RATE_24M: [
        ["pfs", "progression-free", "progression free"],
        [
            "24 month",
            "24 months",
            "24 mo",
            "24mo",
            "24m",
            "2 year",
            "2 years",
            "2 yr",
            "2yr",
            "2 y",
            "2y",
            "24 mth",
            "24 mths",
            "two year",
            "two years",
        ],
    ],
    AttributeType.PFS_RATE_36M: [
        ["pfs", "progression-free", "progression free"],
        [
            "36 month",
            "36 months",
            "36 mo",
            "36mo",
            "36m",
            "3 year",
            "3 years",
            "3 yr",
            "3yr",
            "3 y",
            "3y",
            "36 mth",
            "36 mths",
            "three year",
            "three years",
        ],
    ],
    AttributeType.PFS_RATE_48M: [
        ["pfs", "progression-free", "progression free"],
        [
            "48 month",
            "48 months",
            "48 mo",
            "48mo",
            "48m",
            "4 year",
            "4 years",
            "4 yr",
            "4yr",
            "4 y",
            "4y",
            "48 mth",
            "48 mths",
            "four year",
            "four years",
        ],
    ],
    # OS Family
    AttributeType.MEDIAN_OS: ["os", "overall survival"],
    AttributeType.MEDIAN_FOLLOWUP_OS: [
        ["os", "overall survival"],
        ["follow-up", "followup", "follow up", "median follow"],
    ],
    AttributeType.P_VALUE_OS: [["os", "overall survival"], ["p-value", "p value", "p"]],
    AttributeType.HR_OS: [
        ["os", "overall survival"],  # Group 1: Must have OS
        ["hr", "hazard ratio"],  # Group 2: Must have HR
    ],
    AttributeType.OS_RATE_6M: [
        ["os", "overall survival"],
        [
            "6 month",
            "6 months",
            "6 mo",
            "6m",
            "6 mth",
            "6 mths",
            "six month",
            "six months",
        ],
    ],
    AttributeType.OS_RATE_9M: [
        ["os", "overall survival"],
        [
            "9 month",
            "9 months",
            "9 mo",
            "9m",
            "9 mth",
            "9 mths",
            "nine month",
            "nine months",
        ],
    ],
    AttributeType.OS_RATE_12M: [
        ["os", "overall survival"],
        [
            "12 month",
            "12 months",
            "12 mo",
            "12mo",
            "12m",
            "1 year",
            "1 years",
            "1 yr",
            "1yr",
            "1 y",
            "1y",
            "12 mth",
            "12 mths",
            "one year",
            "twelve month",
            "twelve months",
        ],
    ],
    AttributeType.OS_RATE_18M: [
        ["os", "overall survival"],
        ["18 month", "18 months", "18 mo", "18mo", "18m", "18 mth", "18 mths"],
    ],
    AttributeType.OS_RATE_24M: [
        ["os", "overall survival"],
        [
            "24 month",
            "24 months",
            "24 mo",
            "24mo",
            "24m",
            "2 year",
            "2 years",
            "2 yr",
            "2yr",
            "2 y",
            "2y",
            "24 mth",
            "24 mths",
            "two year",
            "two years",
        ],
    ],
    AttributeType.OS_RATE_36M: [
        ["os", "overall survival"],
        [
            "36 month",
            "36 months",
            "36 mo",
            "36mo",
            "36m",
            "3 year",
            "3 years",
            "3 yr",
            "3yr",
            "3 y",
            "3y",
            "36 mth",
            "36 mths",
            "three year",
            "three years",
        ],
    ],
    AttributeType.OS_RATE_48M: [
        ["os", "overall survival"],
        [
            "48 month",
            "48 months",
            "48 mo",
            "48mo",
            "48m",
            "4 year",
            "4 years",
            "4 yr",
            "4yr",
            "4 y",
            "4y",
            "48 mth",
            "48 mths",
            "four year",
            "four years",
        ],
    ],
    # Response Rates
    AttributeType.OBJECTIVE_RESPONSE_RATE: [
        "orr",
        "objective response rate",
        "response rate",
        "rr",
    ],
    AttributeType.COMPLETE_RESPONSE: ["cr", "complete response"],
    AttributeType.PATHOLOGICAL_COMPLETE_RESPONSE: [
        "pcr",
        "pathological complete response",
        "pathologic complete response",
    ],
    AttributeType.COMPLETE_METABOLIC_RESPONSE: ["cmr", "complete metabolic response"],
    AttributeType.DISEASE_CONTROL_RATE: ["dcr", "disease control rate"],
    AttributeType.CLINICAL_BENEFIT_RATE: ["cbr", "clinical benefit rate"],
    AttributeType.MEDIAN_DOR: ["dor", "duration of response", "duration response"],
    AttributeType.DOR_RATE: ["dor", "duration of response", "duration response"],
    # Other Survival Metrics
    AttributeType.EFS: ["efs", "event-free survival", "event free survival"],
    AttributeType.P_VALUE_EFS: [
        ["efs", "event-free", "event free"],
        ["p-value", "p value", "p"],
    ],
    AttributeType.HR_EFS: [
        ["efs", "event-free", "event free"],  # Group 1: Must have EFS
        ["hr", "hazard ratio"],  # Group 2: Must have HR
    ],
    AttributeType.RFS: [
        "rfs",
        "recurrence-free survival",
        "recurrence free survival",
        "relapse-free survival",
    ],
    AttributeType.P_VALUE_RFS: [
        ["rfs", "recurrence-free", "recurrence free", "relapse-free", "relapse free"],
        ["p-value", "p value", "p"],
    ],
    AttributeType.LENGTH_RFS: ["rfs", "recurrence-free", "relapse-free"],
    AttributeType.HR_RFS: [
        [
            "rfs",
            "recurrence-free",
            "recurrence free",
            "relapse-free",
            "relapse free",
        ],  # Group 1: Must have RFS
        ["hr", "hazard ratio"],  # Group 2: Must have HR
    ],
    AttributeType.MFS: ["mfs", "metastasis-free survival", "metastasis free survival"],
    AttributeType.LENGTH_MFS: ["mfs", "metastasis-free"],
    AttributeType.HR_MFS: [
        ["mfs", "metastasis-free", "metastasis free"],  # Group 1: Must have MFS
        ["hr", "hazard ratio"],  # Group 2: Must have HR
    ],
    # Time-to Metrics
    AttributeType.TTR: ["ttr", "time to response"],
    AttributeType.TTP: ["ttp", "time to progression"],
    AttributeType.TTNT: ["ttnt", "time to next treatment"],
    AttributeType.TTF: ["ttf", "time to failure", "time to treatment failure"],
    # Demographics (only those extracted from abstracts)
    # Note: minimum_age, maximum_age, sex obtained from ClinicalTrials.gov API
    AttributeType.MEDIAN_AGE: ["age", "median age", "years old", "yr", "yrs"],
    AttributeType.NUMBER_OF_PATIENTS: [
        "patient",
        "pts",
        "enrolled",
        "randomized",
        "n=",
    ],
    # Adverse Events
    AttributeType.AE: ["ae", "adverse event"],
    AttributeType.GRADE_3_PLUS_AE: [
        ["ae", "adverse event"],
        ["grade 3", "grade 4", "grade 3-4", "grade ≥3"],
    ],
    AttributeType.AE_LEADING_TO_DISCONTINUATION: [
        ["ae", "adverse event"],
        ["discontinuation", "discontinue", "discontinued"],
    ],
    AttributeType.SERIOUS_AE: [["ae", "adverse event"], ["serious", "sae"]],
    AttributeType.IMMUNE_RELATED_AE: [
        ["ae", "adverse event"],
        ["immune-related", "immune related", "irae"],
    ],
    AttributeType.SERIOUS_IMMUNE_RELATED_AE: [
        ["ae", "adverse event"],
        ["serious"],
        ["immune-related", "immune related", "irae"],
    ],
    AttributeType.AE_LEADING_TO_DEATH: [
        ["ae", "adverse event"],
        ["death", "fatal", "died"],
    ],
    # TEAEs
    AttributeType.TEAE: ["teae", "treatment-emergent", "treatment emergent"],
    AttributeType.GRADE_3_PLUS_TEAE: [
        ["teae", "treatment-emergent", "treatment emergent"],
        ["grade 3", "grade 4", "grade 3-4", "grade ≥3"],
    ],
    AttributeType.GRADE_3_TEAE: [
        ["teae", "treatment-emergent", "treatment emergent"],
        ["grade 3"],
    ],
    AttributeType.GRADE_4_TEAE: [
        ["teae", "treatment-emergent", "treatment emergent"],
        ["grade 4"],
    ],
    AttributeType.GRADE_5_TEAE: [
        ["teae", "treatment-emergent", "treatment emergent"],
        ["grade 5"],
    ],
    AttributeType.TEAE_LEADING_TO_DISCONTINUATION: [
        ["teae", "treatment-emergent", "treatment emergent"],
        ["discontinuation", "discontinue", "discontinued"],
    ],
    AttributeType.TEAE_LEADING_TO_DEATH: [
        ["teae", "treatment-emergent", "treatment emergent"],
        ["death", "fatal", "died"],
    ],
    AttributeType.SERIOUS_TEAE: [
        ["teae", "treatment-emergent", "treatment emergent"],
        ["serious"],
    ],
    AttributeType.TEAE_IMMUNE_RELATED: [
        ["teae", "treatment-emergent", "treatment emergent"],
        ["immune-related", "immune related", "irae"],
    ],
    # TRAEs
    AttributeType.TRAE: ["trae", "treatment-related", "treatment related"],
    AttributeType.GRADE_3_PLUS_TRAE: [
        ["trae", "treatment-related", "treatment related"],
        ["grade 3", "grade 4", "grade 3-4", "grade ≥3"],
    ],
    AttributeType.GRADE_3_TRAE: [
        ["trae", "treatment-related", "treatment related"],
        ["grade 3"],
    ],
    AttributeType.GRADE_4_TRAE: [
        ["trae", "treatment-related", "treatment related"],
        ["grade 4"],
    ],
    AttributeType.GRADE_5_TRAE: [
        ["trae", "treatment-related", "treatment related"],
        ["grade 5"],
    ],
    AttributeType.TRAE_LEADING_TO_DISCONTINUATION: [
        ["trae", "treatment-related", "treatment related"],
        ["discontinuation", "discontinue", "discontinued"],
    ],
    AttributeType.TRAE_LEADING_TO_DEATH: [
        ["trae", "treatment-related", "treatment related"],
        ["death", "fatal", "died"],
    ],
    AttributeType.TRAE_IMMUNE_RELATED: [
        ["trae", "treatment-related", "treatment related"],
        ["immune-related", "immune related", "irae"],
    ],
    AttributeType.SERIOUS_TRAE: [
        ["trae", "treatment-related", "treatment related"],
        ["serious"],
    ],
    # Specific AEs
    AttributeType.CRS: ["crs", "cytokine release syndrome"],
    AttributeType.WBC_DECREASED: ["wbc", "white blood cell", "leukocyte", "decreased"],
}


def get_keywords_for_attribute(attribute_type: AttributeType) -> list[str]:
    """Get keyword filters for an attribute."""
    return ATTRIBUTE_KEYWORDS.get(attribute_type, [])


def chunk_contains_keywords(chunk_content: str, keywords) -> bool:
    """Check if chunk contains required keywords (whole word matching).

    Args:
        chunk_content: Text content to search in
        keywords: Either List[str] for OR matching, or List[List[str]] for grouped AND matching

    Examples:
        ["pfs", "progression-free"]          -> matches if ANY keyword found (OR)
        [["pfs"], ["hr", "hazard ratio"]]    -> matches if keywords from ALL groups found (AND)

    Returns:
        True if keyword criteria are met
    """
    if not keywords:
        return True

    import re

    content_lower = chunk_content.lower()
    # Normalize hyphens and underscores to spaces for matching
    content_normalized = content_lower.replace("-", " ").replace("_", " ")

    # Check if keywords is a list of lists (grouped AND matching)
    if keywords and isinstance(keywords[0], list):
        # Grouped matching: ALL groups must have at least one match
        for group in keywords:
            group_matched = False
            for keyword in group:
                keyword_lower = keyword.lower()
                # Use word boundaries for whole-word matching
                pattern = r"\b" + re.escape(keyword_lower) + r"\b"
                if re.search(pattern, content_normalized):
                    group_matched = True
                    break

            # If any group doesn't match, return False
            if not group_matched:
                return False

        # All groups matched
        return True
    else:
        # Simple list: OR matching (any keyword matches)
        for keyword in keywords:
            keyword_lower = keyword.lower()
            # Use word boundaries for whole-word matching
            pattern = r"\b" + re.escape(keyword_lower) + r"\b"
            if re.search(pattern, content_normalized):
                return True

        return False


def filter_results_by_keywords(
    results: list[SearchResult], keywords: list[str]
) -> tuple[list[SearchResult], list[SearchResult]]:
    """Filter search results by keywords.

    Returns:
        (filtered_results, rejected_results)
    """
    filtered = []
    rejected = []

    for result in results:
        if chunk_contains_keywords(result.chunk.content, keywords):
            filtered.append(result)
        else:
            rejected.append(result)

    return filtered, rejected


class ComprehensiveRetrievalTester:
    """Test retrieval for all numeric attributes across multiple abstracts."""

    def __init__(self, num_abstracts: int = 10, clean_db: bool = True):
        self.num_abstracts = num_abstracts
        self.results: dict[str, Any] = {}

        print("\n🚀 Initializing RAG system...")

        # 🧹 Clean database to prevent duplicates from multiple runs
        if clean_db:
            import shutil
            from pathlib import Path

            db_path = Path("./chroma_db_comprehensive")
            if db_path.exists():
                print(f"🧹 Cleaning existing database at {db_path}...")
                shutil.rmtree(db_path)
                print("✅ Database cleaned")

        self.factory = LangChainServiceFactory(
            ServiceConfiguration(
                chunking_strategy="header_based",
                persist_directory="./chroma_db_comprehensive",
                collection_name="comprehensive_test",
            )
        )

        self.chunking_service = self.factory.create_chunking_service()
        self.embedding_service = self.factory.create_embedding_service()
        self.vector_store = self.factory.create_vector_store()

        # Load RAG query templates
        self.rag_config_loader = RAGConfigLoader()
        self.query_templates = self.rag_config_loader.get_all_templates()

        self.indexed_abstract_ids = []

        print("✅ System initialized")

    async def index_abstracts(self, file_path: str):
        """Index abstracts from file."""
        print(f"\n📥 Indexing {self.num_abstracts} abstracts...")

        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        abstracts = content.split("---\n\n")
        abstracts = [a.strip() for a in abstracts if a.strip()][: self.num_abstracts]

        all_chunks_with_embeddings = []

        for i, abstract_content in enumerate(abstracts, 1):
            match = re.search(r"### Abstract ID: ([0-9]+[A-Z]*)", abstract_content)
            abstract_id = match.group(1) if match else f"unknown_{i}"
            self.indexed_abstract_ids.append(abstract_id)

            print(
                f"  [{i}/{self.num_abstracts}] Indexing abstract {abstract_id}...",
                end="\r",
            )

            config = ChunkingConfiguration(
                strategy=ChunkingStrategy.HEADER_BASED,
                max_chunk_size=1000,
                chunk_overlap=200,
            )

            chunks = await self.chunking_service.chunk_content(
                content=abstract_content,
                configuration=config,
                document_id=abstract_id,
                filename="ASCO_2020.md",
            )

            embedding_config = EmbeddingConfiguration(
                model_name=EmbeddingModel.BIO_BERT_SNLI
            )

            for chunk in chunks:
                embedding = await self.embedding_service.generate_embedding(
                    text=chunk.content, config=embedding_config
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
                    embedding_model="pritamdeka/S-BioBERT-snli-multinli-stsb",
                    created_at=chunk.created_at,
                    embedding_dimension=len(embedding),
                )
                all_chunks_with_embeddings.append(chunk_with_embedding)

        print(f"\n💾 Storing {len(all_chunks_with_embeddings)} chunks...")
        await self.vector_store.store_chunks(all_chunks_with_embeddings)
        print(f"✅ Successfully indexed {len(abstracts)} abstracts")
        print(f"📋 Abstract IDs: {', '.join(self.indexed_abstract_ids)}\n")

    async def test_attribute_retrieval(
        self, attribute_type: AttributeType, abstract_id: str, max_chunks: int = 3
    ) -> dict[str, Any]:
        """Test retrieval for a single attribute in a single abstract."""

        # Get configuration
        required_chunk_types = RAGOptimizationConfig.get_required_chunk_types(
            attribute_type
        )
        queries = self.query_templates.get(
            attribute_type, [f"{attribute_type.value} data"]
        )
        keywords = get_keywords_for_attribute(attribute_type)

        # Build search filters
        search_filters = {"abstract_id": abstract_id}
        if required_chunk_types:
            search_filters["chunk_type"] = required_chunk_types

        # Execute search
        query_text = queries[0] if queries else f"{attribute_type.value}"
        search_query = SearchQuery(
            text=query_text,
            top_k=max_chunks,
            similarity_threshold=0.1,
            metadata_filters=search_filters,
        )

        try:
            results = await self.vector_store.search(search_query)

            unfiltered_count = len(results)
            filtered_count = 0
            rejected_count = 0
            chunk_types = []
            chunks_data = []

            if results:
                chunk_types = [r.chunk.chunk_type.value for r in results]

                # Apply keyword filtering if available
                filtered_results = []
                rejected_results = []

                if keywords:
                    filtered_results, rejected_results = filter_results_by_keywords(
                        results, keywords
                    )
                    filtered_count = len(filtered_results)
                    rejected_count = len(rejected_results)
                else:
                    filtered_results = results
                    filtered_count = unfiltered_count
                    rejected_count = 0

                # Store chunk details
                for result in results:
                    is_filtered = result in filtered_results
                    chunks_data.append(
                        {
                            "content": result.chunk.content[
                                :1000
                            ],  # Limit to 1000 chars
                            "chunk_type": result.chunk.chunk_type.value,
                            "similarity_score": result.similarity_score,
                            "passed_filter": is_filtered,
                            "sequence_number": result.chunk.sequence_number,
                            "metadata": {
                                "is_subchunk": result.chunk.metadata.get(
                                    "is_subchunk", False
                                ),
                                "subchunk_index": result.chunk.metadata.get(
                                    "subchunk_index"
                                ),
                                "total_subchunks": result.chunk.metadata.get(
                                    "total_subchunks"
                                ),
                            },
                        }
                    )

            return {
                "attribute": attribute_type.value,
                "abstract_id": abstract_id,
                "query_text": query_text,
                "keywords": keywords,
                "has_keywords": len(keywords) > 0,
                "tier1_filter": required_chunk_types,
                "unfiltered_count": unfiltered_count,
                "filtered_count": filtered_count,
                "rejected_count": rejected_count,
                "chunk_types": chunk_types,
                "chunks": chunks_data,
                "attribute_present": filtered_count > 0 if keywords else None,
            }

        except Exception as e:
            return {
                "attribute": attribute_type.value,
                "abstract_id": abstract_id,
                "error": str(e),
            }

    async def run_comprehensive_test(self):
        """Test all numeric attributes across all indexed abstracts."""
        print(f"\n{'='*80}")
        print("🔍 COMPREHENSIVE RETRIEVAL TEST")
        print(f"{'='*80}")
        print(
            f"Testing {len(RAGOptimizationConfig.NUMERIC_ATTRIBUTES)} numeric attributes"
        )
        print(f"Across {len(self.indexed_abstract_ids)} abstracts")
        print(
            f"Total queries: {len(RAGOptimizationConfig.NUMERIC_ATTRIBUTES) * len(self.indexed_abstract_ids)}"
        )
        print(f"{'='*80}\n")

        all_results = []
        total_queries = len(RAGOptimizationConfig.NUMERIC_ATTRIBUTES) * len(
            self.indexed_abstract_ids
        )
        current_query = 0

        for attribute_type in sorted(
            RAGOptimizationConfig.NUMERIC_ATTRIBUTES, key=lambda x: x.value
        ):
            for abstract_id in self.indexed_abstract_ids:
                current_query += 1

                print(
                    f"[{current_query}/{total_queries}] Testing {attribute_type.value:40s} in {abstract_id}...",
                    end="\r",
                )

                result = await self.test_attribute_retrieval(
                    attribute_type, abstract_id, max_chunks=5
                )
                all_results.append(result)

        print(f"\n\n✅ Completed {total_queries} queries\n")

        return all_results

    def generate_report(self, results: list[dict[str, Any]], output_file: str = None):
        """Generate summary report."""

        print(f"\n{'='*80}")
        print("📊 RETRIEVAL ANALYSIS REPORT")
        print(f"{'='*80}\n")

        # Overall statistics
        total_queries = len(results)
        queries_with_results = sum(
            1 for r in results if r.get("unfiltered_count", 0) > 0
        )
        queries_with_keywords = sum(1 for r in results if r.get("has_keywords", False))
        queries_filtered_to_zero = sum(
            1
            for r in results
            if r.get("filtered_count", 0) == 0
            and r.get("unfiltered_count", 0) > 0
            and r.get("has_keywords", False)
        )

        total_unfiltered = sum(r.get("unfiltered_count", 0) for r in results)
        total_filtered = sum(
            r.get("filtered_count", 0) for r in results if r.get("has_keywords", False)
        )
        total_rejected = sum(r.get("rejected_count", 0) for r in results)

        print("📈 Overall Statistics:")
        print(f"   Total Queries:              {total_queries}")
        print(
            f"   Queries with Results:       {queries_with_results} ({queries_with_results/total_queries*100:.1f}%)"
        )
        print(
            f"   Queries with Keyword Filter: {queries_with_keywords} ({queries_with_keywords/total_queries*100:.1f}%)"
        )
        print(
            f"   Queries Filtered to Zero:   {queries_filtered_to_zero} ({queries_filtered_to_zero/queries_with_keywords*100:.1f}% of filtered)"
        )
        print(f"\n   Total Chunks Retrieved:     {total_unfiltered}")
        print(f"   Chunks Passed Filter:       {total_filtered}")
        print(
            f"   Chunks Rejected:            {total_rejected} ({total_rejected/total_unfiltered*100:.1f}% if total > 0)"
        )

        # Attribute family statistics
        print(f"\n{'─'*80}")
        print("📊 By Attribute Family:")
        print(f"{'─'*80}\n")

        families = {
            "PFS": ["pfs"],
            "OS": ["os_"],
            "Response": ["response", "cr", "pr", "dor", "dcr", "cbr"],
            "Adverse Events": ["ae", "teae", "trae"],
            "Other Survival": ["efs", "rfs", "mfs", "ttr", "ttp", "ttnt", "ttf"],
            "Demographics": ["age", "patient", "sex"],
        }

        for family, keywords_list in families.items():
            family_results = [
                r
                for r in results
                if any(kw in r.get("attribute", "").lower() for kw in keywords_list)
            ]

            if family_results:
                fam_total = len(family_results)
                fam_with_results = sum(
                    1 for r in family_results if r.get("unfiltered_count", 0) > 0
                )
                fam_filtered_zero = sum(
                    1
                    for r in family_results
                    if r.get("filtered_count", 0) == 0
                    and r.get("unfiltered_count", 0) > 0
                    and r.get("has_keywords", False)
                )

                print(
                    f"{family:20s}: {fam_with_results:3d}/{fam_total:3d} found data ({fam_with_results/fam_total*100:5.1f}%), "
                    f"{fam_filtered_zero:3d} filtered to zero ({fam_filtered_zero/fam_total*100:5.1f}%)"
                )

        # Per-abstract statistics
        print(f"\n{'─'*80}")
        print("📄 By Abstract:")
        print(f"{'─'*80}\n")

        for abstract_id in self.indexed_abstract_ids:
            abstract_results = [
                r for r in results if r.get("abstract_id") == abstract_id
            ]

            abs_with_results = sum(
                1 for r in abstract_results if r.get("unfiltered_count", 0) > 0
            )
            abs_attr_present = sum(
                1 for r in abstract_results if r.get("attribute_present", False)
            )

            print(
                f"Abstract {abstract_id}: {abs_with_results}/{len(abstract_results)} queries returned chunks, "
                f"{abs_attr_present} attributes confirmed present"
            )

        # Most problematic attributes (high rejection rate)
        print(f"\n{'─'*80}")
        print("⚠️  Most Problematic Attributes (High False Positive Rate):")
        print(f"{'─'*80}\n")

        # Group by attribute
        by_attribute = defaultdict(lambda: {"total": 0, "unfiltered": 0, "rejected": 0})
        for r in results:
            if r.get("has_keywords", False):
                attr = r.get("attribute")
                by_attribute[attr]["total"] += 1
                by_attribute[attr]["unfiltered"] += r.get("unfiltered_count", 0)
                by_attribute[attr]["rejected"] += r.get("rejected_count", 0)

        # Calculate rejection rates
        rejection_rates = []
        for attr, stats in by_attribute.items():
            if stats["unfiltered"] > 0:
                rejection_rate = stats["rejected"] / stats["unfiltered"]
                rejection_rates.append((attr, rejection_rate, stats))

        # Sort by rejection rate
        rejection_rates.sort(key=lambda x: x[1], reverse=True)

        for i, (attr, rate, stats) in enumerate(rejection_rates[:10], 1):
            print(
                f"{i:2d}. {attr:40s}: {rate*100:5.1f}% rejected ({stats['rejected']}/{stats['unfiltered']} chunks)"
            )

        # Attributes with no keyword filtering
        print(f"\n{'─'*80}")
        print("⚠️  Attributes WITHOUT Keyword Filtering:")
        print(f"{'─'*80}\n")

        no_keywords = sorted(
            set(r.get("attribute") for r in results if not r.get("has_keywords", False))
        )

        if no_keywords:
            for attr in no_keywords[:10]:
                print(f"   • {attr}")
            if len(no_keywords) > 10:
                print(f"   ... and {len(no_keywords) - 10} more")
        else:
            print("   ✅ All attributes have keyword filtering!")

        # Save to file if requested
        if output_file:
            report_data = {
                "timestamp": datetime.now().isoformat(),
                "num_abstracts": len(self.indexed_abstract_ids),
                "abstract_ids": self.indexed_abstract_ids,
                "num_attributes": len(RAGOptimizationConfig.NUMERIC_ATTRIBUTES),
                "total_queries": total_queries,
                "statistics": {
                    "queries_with_results": queries_with_results,
                    "queries_with_keywords": queries_with_keywords,
                    "queries_filtered_to_zero": queries_filtered_to_zero,
                    "total_unfiltered": total_unfiltered,
                    "total_filtered": total_filtered,
                    "total_rejected": total_rejected,
                },
                "detailed_results": results,
            }

            with open(output_file, "w") as f:
                json.dump(report_data, f, indent=2)

            print(f"\n💾 Full report saved to: {output_file}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test all numeric attributes across first N abstracts"
    )
    parser.add_argument(
        "--abstracts",
        "-n",
        type=int,
        default=10,
        help="Number of abstracts to test (default: 10)",
    )
    parser.add_argument(
        "--output", "-o", type=str, help="Output JSON file for detailed results"
    )
    parser.add_argument(
        "--file",
        type=str,
        default="data/postprocessed/ASCO_Abstracts/ASCO_2020.md",
        help="Input markdown file",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Skip cleaning database (keep existing data - may cause duplicates)",
    )

    args = parser.parse_args()

    # Initialize tester
    tester = ComprehensiveRetrievalTester(
        num_abstracts=args.abstracts,
        clean_db=not args.no_clean,  # Clean by default, skip if --no-clean
    )

    # Check file
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return

    # Index abstracts
    await tester.index_abstracts(str(file_path))

    # Run comprehensive test
    results = await tester.run_comprehensive_test()

    # Generate report
    tester.generate_report(results, output_file=args.output)

    print(f"\n{'='*80}")
    print("✅ TESTING COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(main())
