"""Tests for SQLite database functionality.

Tests the SQLite trials service, database build script, and API integration.
"""

import json
from pathlib import Path

import pytest

from src.app.sqlite_trials_service import SQLiteTrialsService


@pytest.fixture
def sample_json_data():
    """Create sample JSON data for testing."""
    return {
        "abstracts": [
            {
                "abstract_id": "test_abstract_1",
                "file": "test_file.json",
                "total_arms": 2,
                "total_attributes_extracted": 10,
                "overall_confidence": 0.95,
                "processing_time_ms": 100,
                "errors": [],
                "warnings": [],
                "arm_results": {
                    "arm_1": {
                        "arm_id": "arm_1",
                        "arm_name": "pembrolizumab",
                        "attributes": {
                            "AttributeType.CANCER_TYPE": {
                                "value": "Cutaneous Melanoma"
                            },
                            "AttributeType.NCT_NUMBER": {"value": "NCT123456"},
                        },
                    },
                    "arm_2": {
                        "arm_id": "arm_2",
                        "arm_name": "nivolumab",
                        "attributes": {
                            "AttributeType.CANCER_TYPE": {
                                "value": "Cutaneous Melanoma"
                            },
                        },
                    },
                },
            }
        ],
        "publications": [
            {
                "publication_id": "test_pub_1",
                "file": "test_file.json",
                "total_arms": 1,
                "total_attributes_extracted": 8,
                "overall_confidence": 0.90,
                "processing_time_ms": 80,
                "errors": [],
                "warnings": [],
                "arm_results": {
                    "arm_1": {
                        "arm_id": "arm_1",
                        "arm_name": "ipilimumab",
                        "attributes": {
                            "cancer_type": {"value": "Uveal Melanoma"},
                            "AttributeType.NCT_NUMBER": {"value": "NCT789012"},
                        },
                    },
                },
            }
        ],
    }


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test_trials.db"


@pytest.fixture
def temp_json_file(tmp_path, sample_json_data):
    """Create a temporary JSON file with sample data."""
    json_file = tmp_path / "test_data.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(sample_json_data, f)
    return json_file


def test_build_database_script(temp_db_path, temp_json_file):
    """Test that the build_db.py script can create a database."""
    from scripts.build_db import build_database

    # Build database from JSON file
    build_database(temp_db_path, [temp_json_file])

    # Verify database was created
    assert temp_db_path.exists(), "Database file should be created"

    # Verify database has data
    import sqlite3

    conn = sqlite3.connect(str(temp_db_path))
    cursor = conn.execute("SELECT COUNT(*) FROM abstracts")
    count = cursor.fetchone()[0]
    conn.close()

    assert (
        count == 2
    ), f"Should have 2 records (1 abstract + 1 publication), got {count}"


def test_sqlite_service_load_data(temp_db_path, temp_json_file):
    """Test that SQLiteTrialsService can load data from database."""
    from scripts.build_db import build_database

    # Build database first
    build_database(temp_db_path, [temp_json_file])

    # Create service instance
    service = SQLiteTrialsService(db_path=temp_db_path)

    # Load data
    abstracts = service._load_json_files()

    # Verify data loaded correctly
    assert len(abstracts) == 2, f"Should load 2 records, got {len(abstracts)}"

    # Verify abstract data
    abstract = next(
        (a for a in abstracts if a.get("abstract_id") == "test_abstract_1"), None
    )
    assert abstract is not None, "Should find test abstract"
    assert abstract["total_arms"] == 2
    assert len(abstract["arm_results"]) == 2

    # Verify publication data
    publication = next(
        (a for a in abstracts if a.get("publication_id") == "test_pub_1"), None
    )
    assert publication is not None, "Should find test publication"
    assert publication["total_arms"] == 1


def test_sqlite_service_get_all_trials(temp_db_path, temp_json_file):
    """Test get_all_trials method."""
    from scripts.build_db import build_database

    # Build database first
    build_database(temp_db_path, [temp_json_file])

    # Create service instance
    service = SQLiteTrialsService(db_path=temp_db_path)

    # Get trials with pagination
    trials, total = service.get_all_trials(skip=0, limit=10)

    assert total == 2, f"Should have 2 total records, got {total}"
    assert len(trials) == 2, f"Should return 2 trials, got {len(trials)}"

    # Test pagination
    trials_page1, _ = service.get_all_trials(skip=0, limit=1)
    trials_page2, _ = service.get_all_trials(skip=1, limit=1)

    assert len(trials_page1) == 1, "First page should have 1 item"
    assert len(trials_page2) == 1, "Second page should have 1 item"
    assert (
        trials_page1[0]["id"] != trials_page2[0]["id"]
    ), "Pages should have different items"


def test_sqlite_service_get_full_abstract(temp_db_path, temp_json_file):
    """Test get_full_abstract_by_id method."""
    from scripts.build_db import build_database

    # Build database first
    build_database(temp_db_path, [temp_json_file])

    # Create service instance
    service = SQLiteTrialsService(db_path=temp_db_path)

    # Get abstract by ID
    abstract = service.get_full_abstract_by_id("test_abstract_1")
    assert abstract is not None, "Should find abstract by ID"
    assert abstract["abstract_id"] == "test_abstract_1"
    assert abstract["total_arms"] == 2

    # Get publication by ID
    publication = service.get_full_abstract_by_id("test_pub_1")
    assert publication is not None, "Should find publication by ID"
    assert publication["publication_id"] == "test_pub_1"

    # Test non-existent ID
    not_found = service.get_full_abstract_by_id("nonexistent")
    assert not_found is None, "Should return None for non-existent ID"


def test_sqlite_service_nonexistent_db():
    """Test that service handles non-existent database gracefully."""
    service = SQLiteTrialsService(db_path=Path("/nonexistent/path/trials.db"))

    # Should return empty list, not raise exception
    abstracts = service._load_json_files()
    assert abstracts == [], "Should return empty list for non-existent database"

    # get_all_trials should also handle gracefully
    trials, total = service.get_all_trials()
    assert total == 0, "Should return 0 total for non-existent database"
    assert len(trials) == 0, "Should return empty list for non-existent database"


def test_api_with_sqlite_data_source(temp_db_path, temp_json_file):
    """Test that API endpoint works with SQLite data source."""
    import os

    from scripts.build_db import build_database

    # Build database first
    build_database(temp_db_path, [temp_json_file])

    # Set environment variable to use SQLite
    original_source = os.environ.get("TRIALS_DATA_SOURCE")
    original_db_path = os.environ.get("TRIALS_DB_PATH")

    try:
        os.environ["TRIALS_DATA_SOURCE"] = "sqlite"
        os.environ["TRIALS_DB_PATH"] = str(temp_db_path)

        # Import after setting env vars
        from src.app.api import get_trials_service

        # Get service (should be SQLite service)
        service = get_trials_service()

        # Verify it's SQLite service
        assert isinstance(
            service, SQLiteTrialsService
        ), "Should return SQLiteTrialsService when TRIALS_DATA_SOURCE=sqlite"

        # Test loading data
        abstracts = service._load_json_files()
        assert len(abstracts) == 2, "Should load 2 records from SQLite"

    finally:
        # Restore original environment
        if original_source is not None:
            os.environ["TRIALS_DATA_SOURCE"] = original_source
        elif "TRIALS_DATA_SOURCE" in os.environ:
            del os.environ["TRIALS_DATA_SOURCE"]

        if original_db_path is not None:
            os.environ["TRIALS_DB_PATH"] = original_db_path
        elif "TRIALS_DB_PATH" in os.environ:
            del os.environ["TRIALS_DB_PATH"]


def test_build_db_filters_no_arms(temp_db_path, tmp_path):
    """Test that build_db filters out items with no treatment arms."""
    # Create JSON with item that has "No treatment arms identified" error
    json_data = {
        "abstracts": [
            {
                "abstract_id": "valid_abstract",
                "total_arms": 1,
                "errors": [],
                "arm_results": {"arm_1": {"arm_id": "arm_1", "arm_name": "test"}},
            },
            {
                "abstract_id": "invalid_abstract",
                "total_arms": 0,
                "errors": ["No treatment arms identified"],
                "arm_results": {},
            },
        ]
    }

    json_file = tmp_path / "test_filter.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(json_data, f)

    from scripts.build_db import build_database

    # Build database
    build_database(temp_db_path, [json_file])

    # Verify only valid abstract is in database
    import sqlite3

    conn = sqlite3.connect(str(temp_db_path))
    cursor = conn.execute("SELECT abstract_id FROM abstracts")
    abstract_ids = [row[0] for row in cursor.fetchall()]
    conn.close()

    assert "valid_abstract" in abstract_ids, "Valid abstract should be in database"
    assert (
        "invalid_abstract" not in abstract_ids
    ), "Invalid abstract should be filtered out"


def test_api_endpoint_with_sqlite(temp_db_path, temp_json_file):
    """Test that the analytics API endpoint works with SQLite data source."""
    import os

    import httpx
    from httpx import ASGITransport

    from scripts.build_db import build_database

    # Build database first
    build_database(temp_db_path, [temp_json_file])

    # Set environment variable to use SQLite
    original_source = os.environ.get("TRIALS_DATA_SOURCE")
    original_db_path = os.environ.get("TRIALS_DB_PATH")

    try:
        os.environ["TRIALS_DATA_SOURCE"] = "sqlite"
        os.environ["TRIALS_DB_PATH"] = str(temp_db_path)

        # Import app after setting env vars (to pick up the new config)
        # We need to reload the module to get the new env vars
        import importlib

        from src.app import api

        importlib.reload(api)

        # Create test client
        transport = ASGITransport(app=api.app)
        client = httpx.AsyncClient(transport=transport, base_url="http://testserver")

        # Test analytics endpoint
        import asyncio

        async def test_endpoint():
            response = await client.get("/api/analytics/data?limit=10")
            assert (
                response.status_code == 200
            ), f"Expected 200, got {response.status_code}"

            data = response.json()
            assert "abstracts" in data, "Response should contain abstracts"
            assert "total_abstracts" in data, "Response should contain total_abstracts"
            assert (
                data["total_abstracts"] == 2
            ), f"Should have 2 abstracts, got {data['total_abstracts']}"
            assert (
                len(data["abstracts"]) == 2
            ), f"Should return 2 abstracts, got {len(data['abstracts'])}"

            # Test filtering
            response_filtered = await client.get(
                "/api/analytics/data?resource_type=publication&limit=10"
            )
            assert response_filtered.status_code == 200
            filtered_data = response_filtered.json()
            # Should only have publications
            assert filtered_data["total_abstracts"] == 1, "Should have 1 publication"

            await client.aclose()

        # Run async test
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(test_endpoint())

    finally:
        # Restore original environment
        if original_source is not None:
            os.environ["TRIALS_DATA_SOURCE"] = original_source
        elif "TRIALS_DATA_SOURCE" in os.environ:
            del os.environ["TRIALS_DATA_SOURCE"]

        if original_db_path is not None:
            os.environ["TRIALS_DB_PATH"] = original_db_path
        elif "TRIALS_DB_PATH" in os.environ:
            del os.environ["TRIALS_DB_PATH"]

        # Reload module to restore original config
        import importlib

        from src.app import api

        importlib.reload(api)
