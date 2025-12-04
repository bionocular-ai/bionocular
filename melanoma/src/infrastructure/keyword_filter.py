"""Tier 3 keyword filtering for RAG retrieval.

This module provides keyword-based filtering to eliminate semantic similarity
false positives from RAG retrieval results.

Key features:
- Whole-word matching using regex word boundaries
- Simple OR matching (any keyword matches)
- Grouped AND matching (all groups must match)
- Hyphen and underscore normalization
"""

import logging
import re
from typing import Union

logger = logging.getLogger(__name__)


def chunk_contains_keywords(
    chunk_content: str, keywords: Union[list[str], list[list[str]]]
) -> bool:
    """Check if chunk contains required keywords (whole word matching).

    This function supports two keyword matching modes:
    1. Simple OR matching: List[str] - matches if ANY keyword is found
    2. Grouped AND matching: List[List[str]] - matches if keywords from ALL groups are found

    Examples:
        Simple OR: ["pfs", "progression-free"] -> matches if ANY keyword found
        Grouped AND: [["pfs"], ["hr", "hazard ratio"]] -> matches if keywords from ALL groups found

    Args:
        chunk_content: Text content to search in
        keywords: Either List[str] for OR matching, or List[List[str]] for grouped AND matching

    Returns:
        True if keyword criteria are met, False otherwise
    """
    if not keywords:
        return True

    # Normalize content: lowercase and replace hyphens/underscores with spaces
    # This allows "3.05-yr" to match "3.05 yr" and "event-free" to match "event free"
    content_lower = chunk_content.lower()
    content_normalized = content_lower.replace("-", " ").replace("_", " ")

    # Check if keywords is a list of lists (grouped AND matching)
    if keywords and isinstance(keywords[0], list):
        # Grouped matching: ALL groups must have at least one match
        for group in keywords:
            group_matched = False
            for keyword in group:
                keyword_lower = keyword.lower()
                # Use word boundaries to match whole words only
                # This prevents "cr" from matching "across"
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


def validate_keywords(keywords: Union[list[str], list[list[str]]]) -> bool:
    """Validate keyword structure.

    Args:
        keywords: Keywords to validate

    Returns:
        True if keywords are valid, False otherwise
    """
    if not keywords:
        return False

    if not isinstance(keywords, list):
        return False

    # Check if grouped (List[List[str]]) or simple (List[str])
    if keywords and isinstance(keywords[0], list):
        # Grouped: validate all groups are non-empty string lists
        for group in keywords:
            if not isinstance(group, list) or not group:
                return False
            for keyword in group:
                if not isinstance(keyword, str) or not keyword.strip():
                    return False
    else:
        # Simple: validate all are non-empty strings
        for keyword in keywords:
            if not isinstance(keyword, str) or not keyword.strip():
                return False

    return True
