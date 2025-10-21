"""File path-based extractor for simple attributes.

This module provides simple extraction logic for attributes that can be
determined from file paths, avoiding the need for LLM calls.
"""

import logging
import re
from pathlib import Path
from typing import Optional

from ..domain.extraction_models import AttributeType

logger = logging.getLogger(__name__)


class FilePathExtractor:
    """Extractor for attributes that can be determined from file paths."""

    def __init__(self):
        """Initialize file path extractor."""
        self.conference_patterns = {
            "ASCO": r"ASCO",
            "ESMO": r"ESMO",
        }
        self.year_pattern = r"(\d{4})"
        logger.info("File path extractor initialized")

    def extract_conference_from_path(self, file_path: str) -> Optional[str]:
        """Extract conference from file path.

        Args:
            file_path: Path to the file (e.g., "data/postprocessed/ASCO_Abstracts/ASCO_2020.md")

        Returns:
            Conference abbreviation (ASCO or ESMO) or None if not found
        """
        try:
            path_obj = Path(file_path)

            # Check each directory and file name component
            for part in path_obj.parts:
                for conference, pattern in self.conference_patterns.items():
                    if re.search(pattern, part, re.IGNORECASE):
                        logger.debug(
                            f"Extracted conference '{conference}' from path: {file_path}"
                        )
                        return conference

            logger.debug(f"No conference found in path: {file_path}")
            return None

        except Exception as e:
            logger.error(f"Error extracting conference from path {file_path}: {e}")
            return None

    def extract_year_from_path(self, file_path: str) -> Optional[str]:
        """Extract year from file path.

        Args:
            file_path: Path to the file (e.g., "data/postprocessed/ASCO_Abstracts/ASCO_2020.md")

        Returns:
            4-digit year string or None if not found
        """
        try:
            path_obj = Path(file_path)

            # Check each directory and file name component
            for part in path_obj.parts:
                match = re.search(self.year_pattern, part)
                if match:
                    year = match.group(1)
                    # Validate year range
                    if 1990 <= int(year) <= 2030:
                        logger.debug(f"Extracted year '{year}' from path: {file_path}")
                        return year

            logger.debug(f"No valid year found in path: {file_path}")
            return None

        except Exception as e:
            logger.error(f"Error extracting year from path {file_path}: {e}")
            return None

    def extract_attribute_from_path(
        self, attribute_type: AttributeType, file_path: str
    ) -> Optional[str]:
        """Extract attribute value from file path.

        Args:
            attribute_type: Type of attribute to extract
            file_path: Path to the file

        Returns:
            Extracted value or None if not found
        """
        if attribute_type == AttributeType.CONFERENCE:
            return self.extract_conference_from_path(file_path)
        elif attribute_type == AttributeType.PUBLISHED_YEAR:
            return self.extract_year_from_path(file_path)
        else:
            logger.debug(
                f"Attribute {attribute_type} not supported by file path extractor"
            )
            return None

    def can_extract_from_path(self, attribute_type: AttributeType) -> bool:
        """Check if an attribute can be extracted from file path.

        Args:
            attribute_type: Type of attribute to check

        Returns:
            True if can be extracted from path, False otherwise
        """
        return attribute_type in [
            AttributeType.CONFERENCE,
            AttributeType.PUBLISHED_YEAR,
        ]
