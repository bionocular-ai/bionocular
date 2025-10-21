"""Test script for file path extraction functionality."""

import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

# Import after path modification
from src.domain.extraction_models import AttributeType  # noqa: E402
from src.infrastructure.file_path_extractor import FilePathExtractor  # noqa: E402


def test_file_path_extraction():
    """Test file path extraction for Conference and Published Year."""

    extractor = FilePathExtractor()

    # Test cases
    test_cases = [
        "data/postprocessed/ASCO_Abstracts/ASCO_2020.md",
        "data/postprocessed/ESMO_Abstracts/ESMO_2021.md",
        "data/postprocessed/ASCO_Abstracts/ASCO_2019.md",
        "data/postprocessed/ESMO_Abstracts/ESMO_2022.md",
        "data/postprocessed/ASCO_Abstracts/ASCO_2023.md",
    ]

    print("Testing File Path Extraction")
    print("=" * 50)

    for file_path in test_cases:
        print(f"\nFile Path: {file_path}")

        # Test Conference extraction
        conference = extractor.extract_conference_from_path(file_path)
        print(f"Conference: {conference}")

        # Test Year extraction
        year = extractor.extract_year_from_path(file_path)
        print(f"Year: {year}")

        # Test attribute extraction
        conference_attr = extractor.extract_attribute_from_path(
            AttributeType.CONFERENCE, file_path
        )
        year_attr = extractor.extract_attribute_from_path(
            AttributeType.PUBLISHED_YEAR, file_path
        )

        print(f"Conference Attribute: {conference_attr}")
        print(f"Year Attribute: {year_attr}")

        # Test can_extract_from_path
        can_extract_conf = extractor.can_extract_from_path(AttributeType.CONFERENCE)
        can_extract_year = extractor.can_extract_from_path(AttributeType.PUBLISHED_YEAR)
        can_extract_other = extractor.can_extract_from_path(AttributeType.NCT_NUMBER)

        print(f"Can extract Conference: {can_extract_conf}")
        print(f"Can extract Year: {can_extract_year}")
        print(f"Can extract NCT_NUMBER: {can_extract_other}")

        print("-" * 30)


if __name__ == "__main__":
    test_file_path_extraction()
