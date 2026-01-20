#!/usr/bin/env python3
"""Test frontend integration - verify API calls match frontend expectations."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import os

import httpx
from httpx import ASGITransport

os.environ["TRIALS_DATA_SOURCE"] = "sqlite"
os.environ["TRIALS_DB_PATH"] = str(
    Path(__file__).parent / "data" / "trials_db" / "trials.db"
)

from src.app.api import app


async def test_frontend_api_calls():
    """Test API calls that the frontend makes."""
    print("=" * 60)
    print("Frontend Integration Tests")
    print("=" * 60)

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        # Test 1: Default analytics call (what frontend does on page load)
        print("\n1. Testing default analytics call (page load)...")
        response = await client.get("/api/analytics/data?limit=2000")
        assert response.status_code == 200
        data = response.json()
        print(f"   ✅ Status: {response.status_code}")
        print(f"   ✅ Total abstracts: {data['total_abstracts']}")
        print(f"   ✅ Returned: {len(data['abstracts'])}")
        assert "abstracts" in data
        assert "total_abstracts" in data
        assert "total_arms" in data
        assert "total_attributes_extracted" in data

        # Test 2: Filter by resource_type (publication)
        print("\n2. Testing resource_type=publication filter...")
        response = await client.get(
            "/api/analytics/data?resource_type=publication&limit=2000"
        )
        assert response.status_code == 200
        data = response.json()
        print(f"   ✅ Publications: {data['total_abstracts']}")
        # Verify all returned items are publications
        for abstract in data["abstracts"][:5]:  # Check first 5
            assert (
                abstract.get("publication_id") is not None
            ), "Should have publication_id"
            assert (
                abstract.get("abstract_id") is None or abstract.get("file") is None
            ), "Should not have abstract_id or file"

        # Test 3: Filter by resource_type (conference)
        print("\n3. Testing resource_type=conference filter...")
        response = await client.get(
            "/api/analytics/data?resource_type=conference&limit=2000"
        )
        assert response.status_code == 200
        data = response.json()
        print(f"   ✅ Conference abstracts: {data['total_abstracts']}")
        # Verify all returned items are conference abstracts
        for abstract in data["abstracts"][:5]:  # Check first 5
            assert (
                abstract.get("abstract_id") is not None
                or abstract.get("file") is not None
            ), "Should have abstract_id or file"

        # Test 4: Filter by therapy_type
        print("\n4. Testing therapy_type filter...")
        response = await client.get(
            "/api/analytics/data?therapy_type=Immunotherapy&limit=2000"
        )
        assert response.status_code == 200
        data = response.json()
        print(f"   ✅ Immunotherapy: {data['total_abstracts']} abstracts")

        # Test 5: Filter by funding_type
        print("\n5. Testing funding_type filter...")
        response = await client.get(
            "/api/analytics/data?funding_type=industry&limit=2000"
        )
        assert response.status_code == 200
        data = response.json()
        print(f"   ✅ Industry-funded: {data['total_abstracts']} abstracts")

        # Test 6: Combined filters (typical frontend usage)
        print("\n6. Testing combined filters (typical frontend usage)...")
        response = await client.get(
            "/api/analytics/data?resource_type=publication&therapy_type=Immunotherapy&funding_type=industry&limit=2000"
        )
        assert response.status_code == 200
        data = response.json()
        print(f"   ✅ Combined filters: {data['total_abstracts']} abstracts")

        # Test 7: Verify response structure matches frontend expectations
        print("\n7. Testing response structure...")
        response = await client.get("/api/analytics/data?limit=1")
        assert response.status_code == 200
        data = response.json()

        # Check required fields
        required_fields = [
            "abstracts",
            "total_abstracts",
            "total_arms",
            "total_attributes_extracted",
            "average_confidence",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Check abstract structure
        if data["abstracts"]:
            abstract = data["abstracts"][0]
            assert "arm_results" in abstract, "Abstract should have arm_results"
            assert isinstance(
                abstract["arm_results"], dict
            ), "arm_results should be a dict"
            print("   ✅ Response structure valid")
            print(f"   ✅ Sample abstract has {len(abstract['arm_results'])} arms")

        # Test 8: Verify filters are applied correctly (no client-side filtering needed)
        print("\n8. Testing filter correctness...")
        # Get all publications
        response_all = await client.get(
            "/api/analytics/data?resource_type=publication&limit=2000"
        )
        data_all = response_all.json()
        total_publications = data_all["total_abstracts"]

        # Get first page
        response_page1 = await client.get(
            "/api/analytics/data?resource_type=publication&limit=10"
        )
        data_page1 = response_page1.json()

        # Verify all items in page1 are publications
        for abstract in data_page1["abstracts"]:
            assert (
                abstract.get("publication_id") is not None
            ), "All items should be publications"

        print(
            f"   ✅ Filter applied correctly: {len(data_page1['abstracts'])} publications on page 1"
        )
        print(f"   ✅ Total publications: {total_publications}")

        print("\n" + "=" * 60)
        print("✅ All frontend integration tests passed!")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_frontend_api_calls())
