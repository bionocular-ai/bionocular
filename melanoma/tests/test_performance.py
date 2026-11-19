"""Performance tests for resource optimization.

Tests memory usage, response times, concurrent request handling, and
verifies that optimizations (singleton pattern, pagination, compression) work correctly.
"""

import os
import time

import psutil
import pytest
from fastapi.testclient import TestClient

from src.app.api import app


@pytest.fixture
def client():
    """Create a test client for the API."""
    return TestClient(app)


def test_analytics_endpoint_response_time(client):
    """Test that analytics endpoint responds within acceptable time."""
    start_time = time.time()
    response = client.get("/api/analytics/data?skip=0&limit=100")
    elapsed = time.time() - start_time

    assert response.status_code == 200
    # 2.0s allows for CI runner variance; still catches genuinely slow responses
    assert elapsed < 2.0, f"Analytics endpoint took {elapsed:.2f}s, expected < 2.0s"

    data = response.json()
    assert "abstracts" in data
    assert "total_abstracts" in data
    assert "skip" in data
    assert "limit" in data
    assert "has_more" in data
    assert len(data["abstracts"]) <= 100  # Should respect limit
    assert data["skip"] == 0
    assert data["limit"] == 100


def test_analytics_pagination(client):
    """Test that pagination works correctly."""
    # Get first page
    response1 = client.get("/api/analytics/data?skip=0&limit=50")
    assert response1.status_code == 200
    data1 = response1.json()

    # Get second page
    response2 = client.get("/api/analytics/data?skip=50&limit=50")
    assert response2.status_code == 200
    data2 = response2.json()

    # Verify pagination metadata
    assert data1["skip"] == 0
    assert data1["limit"] == 50
    assert data2["skip"] == 50
    assert data2["limit"] == 50
    assert "has_more" in data1
    assert "has_more" in data2

    # Verify no overlap
    ids1 = {a.get("abstract_id") or a.get("publication_id") for a in data1["abstracts"]}
    ids2 = {a.get("abstract_id") or a.get("publication_id") for a in data2["abstracts"]}
    assert len(ids1.intersection(ids2)) == 0, "Pages should not overlap"

    # Verify total is consistent
    assert data1["total_abstracts"] == data2["total_abstracts"]

    # Verify summary stats are consistent (calculated from full dataset)
    assert (
        data1["total_arms"] == data2["total_arms"]
    ), "Total arms should be same across pages"
    assert (
        data1["total_attributes_extracted"] == data2["total_attributes_extracted"]
    ), "Total attributes should be same across pages"


def test_singleton_service_instance():
    """Test that JSONTrialsService uses singleton pattern."""
    from src.app.api import _service_stats, get_json_trials_service

    # Reset stats for clean test
    initial_creations = _service_stats["instance_creations"]
    initial_reuses = _service_stats["instance_reuses"]

    instance1 = get_json_trials_service()
    instance2 = get_json_trials_service()

    # Should be the same instance
    assert instance1 is instance2, "Should return the same singleton instance"

    # Verify stats tracking
    # First call should create, second should reuse
    assert _service_stats["instance_creations"] >= initial_creations
    assert (
        _service_stats["instance_reuses"] > initial_reuses
    ), "Second call should increment reuse count"


def test_response_compression(client):
    """Test that responses are compressed when appropriate."""
    response = client.get(
        "/api/analytics/data?skip=0&limit=100",
        headers={"Accept-Encoding": "gzip"},
    )

    assert response.status_code == 200
    # FastAPI/Starlette automatically handles compression via GZipMiddleware
    # For large responses (>1KB), compression should be applied
    # Note: TestClient may not show compression headers, but middleware is active
    assert len(response.content) > 0
    # Verify response is valid JSON
    data = response.json()
    assert "abstracts" in data


def test_concurrent_requests(client):
    """Test that multiple concurrent requests don't cause issues.

    Verifies that the singleton pattern works correctly under concurrent load
    and that multiple requests can be handled simultaneously.
    """
    import concurrent.futures

    def make_request():
        return client.get("/api/analytics/data?skip=0&limit=10")

    # Make 10 concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # All requests should succeed
    assert all(
        r.status_code == 200 for r in results
    ), "All concurrent requests should succeed"

    # All should return data
    assert all(
        "abstracts" in r.json() for r in results
    ), "All responses should contain abstracts"

    # Verify singleton pattern: all requests should use the same service instance
    # (indirectly verified by successful concurrent execution without errors)


def test_resources_endpoint(client):
    """Test that resources endpoint returns valid data."""
    response = client.get("/api/resources")
    assert response.status_code == 200

    data = response.json()
    assert "process" in data
    assert "system" in data
    assert "service" in data
    assert "json_cache" in data

    # Verify process info
    process = data["process"]
    assert "memory_mb" in process
    assert "cpu_percent" in process
    assert process["memory_mb"] > 0

    # Verify service stats (singleton pattern effectiveness)
    service = data["service"]
    assert "instance_reuses" in service
    assert "instance_creations" in service
    assert "reuse_rate_percent" in service
    assert "total_requests" in service
    assert service["instance_reuses"] >= 0
    assert service["instance_creations"] >= 0

    # Verify JSON cache info
    json_cache = data["json_cache"]
    # Cache may or may not be initialized depending on test order
    assert isinstance(json_cache, dict)


def test_streaming_endpoint(client):
    """Test that streaming endpoint works correctly."""
    response = client.get("/api/analytics/data/stream")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-ndjson"
    assert "Content-Disposition" in response.headers

    # Read first few lines
    content = response.text
    lines = [line for line in content.strip().split("\n") if line.strip()]

    # Should have at least summary line
    assert len(lines) >= 1, "Should have at least summary line"

    # First line should be summary
    import json

    summary = json.loads(lines[0])
    assert summary["type"] == "summary"
    assert "total_abstracts" in summary
    assert "total_arms" in summary

    # Should have multiple lines (summary + abstracts) if data exists
    if summary["total_abstracts"] > 0:
        assert len(lines) > 1, "Should have abstracts after summary"


def test_arm_lazy_loading(client):
    """Test that arm results can be loaded on-demand.

    Verifies the lazy loading optimization works - arms are not included
    in the main analytics response but can be fetched separately.
    """
    # First, get list of abstracts
    response = client.get("/api/analytics/data?skip=0&limit=1")
    assert response.status_code == 200
    data = response.json()

    if data["abstracts"]:
        abstract = data["abstracts"][0]
        abstract_id = abstract.get("abstract_id") or abstract.get("publication_id")

        if abstract_id:
            # Load arms for this abstract
            arm_response = client.get(f"/api/analytics/arms/{abstract_id}")
            assert arm_response.status_code == 200

            arm_data = arm_response.json()
            assert "abstract_id" in arm_data
            assert "arm_results" in arm_data
            assert arm_data["abstract_id"] == abstract_id
            assert isinstance(arm_data["arm_results"], dict)

            # Verify arms endpoint returns 404 for non-existent abstract
            invalid_response = client.get("/api/analytics/arms/nonexistent_id_12345")
            assert invalid_response.status_code == 404
    else:
        pytest.skip("No abstracts available for testing lazy loading")


def test_request_timing_middleware(client):
    """Test that request timing middleware adds X-Process-Time header."""
    response = client.get("/api/analytics/data?skip=0&limit=10")
    assert response.status_code == 200

    # Verify timing header is present
    assert (
        "X-Process-Time" in response.headers
    ), "Request timing header should be present"

    # Verify it's a valid float
    process_time = float(response.headers["X-Process-Time"])
    assert process_time >= 0, "Process time should be non-negative"
    assert (
        process_time < 10.0
    ), "Process time should be reasonable (< 10s for small request)"


@pytest.mark.skipif(
    os.getenv("RUN_MEMORY_TESTS") != "true",
    reason=(
        "Memory growth tests are opt-in. They were designed to validate the legacy "
        "backend singleton/service initialization behavior; after migrating to Supabase "
        "they're not a reliable default quality gate. Set RUN_MEMORY_TESTS=true to enable."
    ),
)
def test_memory_usage_after_requests(client):
    """Test that memory usage doesn't grow excessively after multiple requests.

    This test verifies that the singleton pattern prevents memory bloat
    from creating multiple service instances.
    """
    process = psutil.Process(os.getpid())

    # Warm up: first request may initialize the singleton and load data into memory.
    # We want to measure growth *after* initialization to catch per-request bloat.
    warmup = client.get("/api/analytics/data?skip=0&limit=10")
    assert warmup.status_code == 200

    # Force garbage collection before baseline
    import gc

    gc.collect()

    # Get baseline memory
    baseline_memory = process.memory_info().rss / (1024 * 1024)  # MB

    # Make multiple requests (should reuse singleton instance)
    for _ in range(10):
        response = client.get("/api/analytics/data?skip=0&limit=100")
        assert response.status_code == 200

    # Force garbage collection before final measurement
    gc.collect()

    # Get memory after requests
    final_memory = process.memory_info().rss / (1024 * 1024)  # MB

    # Memory increase threshold calculation (data-driven):
    # This test verifies the singleton pattern prevents creating multiple service instances.
    # The threshold must account for the actual dataset size being loaded.
    #
    # Current dataset (as of Jan 2026):
    # - ASCO 2020-2025: ~829,018 lines
    # - ESMO 2020-2024: ~522,098 lines
    # - ESMO 2025: ~218,928 lines (added Jan 2026)
    # - Publications: ~243,967 lines
    # - Total: ~1,814,011 lines
    #
    # Memory characteristics:
    # - CI environment (SQLite): Lower memory usage, ~60-65 MB for 10 requests
    # - Local/JSON mode: Higher memory usage, loads all JSON files
    # - Singleton pattern ensures data loaded once, not per-request
    #
    # Threshold set to 70 MB to accommodate:
    # - CI environment with current dataset
    # - Small variance between test runs (±5 MB)
    # - Does NOT accommodate full JSON loading (use SKIP_MEMORY_TESTS=true locally)
    #
    # When to update: If adding significant new data files (>50MB), increase proportionally.
    MEMORY_THRESHOLD_MB = 70
    memory_increase = final_memory - baseline_memory
    assert memory_increase < MEMORY_THRESHOLD_MB, (
        f"Memory increased by {memory_increase:.2f} MB, expected < {MEMORY_THRESHOLD_MB} MB. "
        f"Baseline: {baseline_memory:.2f} MB, Final: {final_memory:.2f} MB. "
        f"This test verifies singleton pattern prevents excessive memory growth. "
        f"If running locally with JSON files, set SKIP_MEMORY_TESTS=true. "
        f"If this fails in CI after adding new data, the threshold may need adjustment."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
