#!/usr/bin/env python3
"""Test script to verify SQLite database integration with API endpoints."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

import httpx
from httpx import ASGITransport

# Set environment variables before importing app
os.environ["TRIALS_DATA_SOURCE"] = "sqlite"
db_path = Path(__file__).parent / "data" / "trials_db" / "trials.db"
os.environ["TRIALS_DB_PATH"] = str(db_path)
print(f"Using database at: {db_path}")
print(f"Database exists: {db_path.exists()}")

from src.app.api import app


async def test_sqlite_api():
    """Test API endpoints with SQLite data source."""
    print("=" * 60)
    print("Testing SQLite Database Integration")
    print("=" * 60)
    
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Test 1: Verify service is using SQLite
        print("\n1. Testing service type...")
        from src.app.api import get_trials_service
        service = get_trials_service()
        service_type = type(service).__name__
        print(f"   ✅ Service type: {service_type}")
        assert service_type == "SQLiteTrialsService", f"Expected SQLiteTrialsService, got {service_type}"
        
        # Test 2: Basic analytics endpoint
        print("\n2. Testing /api/analytics/data endpoint...")
        response = await client.get("/api/analytics/data?limit=5")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        print(f"   ✅ Status: {response.status_code}")
        print(f"   ✅ Total abstracts: {data['total_abstracts']}")
        print(f"   ✅ Returned {len(data['abstracts'])} abstracts")
        assert data["total_abstracts"] == 978, f"Expected 978, got {data['total_abstracts']}"
        
        # Test 3: Filtering by resource type (publications)
        print("\n3. Testing filtering by resource_type=publication...")
        response = await client.get("/api/analytics/data?resource_type=publication&limit=10")
        assert response.status_code == 200
        data = response.json()
        print(f"   ✅ Status: {response.status_code}")
        print(f"   ✅ Publications found: {data['total_abstracts']}")
        assert data["total_abstracts"] == 69, f"Expected 69 publications, got {data['total_abstracts']}"
        
        # Test 4: Filtering by resource type (conference)
        print("\n4. Testing filtering by resource_type=conference...")
        response = await client.get("/api/analytics/data?resource_type=conference&limit=10")
        assert response.status_code == 200
        data = response.json()
        print(f"   ✅ Status: {response.status_code}")
        print(f"   ✅ Conference abstracts found: {data['total_abstracts']}")
        assert data["total_abstracts"] == 909, f"Expected 909 conference abstracts, got {data['total_abstracts']}"
        
        # Test 5: Pagination
        print("\n5. Testing pagination...")
        response1 = await client.get("/api/analytics/data?skip=0&limit=5")
        response2 = await client.get("/api/analytics/data?skip=5&limit=5")
        data1 = response1.json()
        data2 = response2.json()
        print(f"   ✅ Page 1: {len(data1['abstracts'])} items")
        print(f"   ✅ Page 2: {len(data2['abstracts'])} items")
        print(f"   ✅ Has more: {data1.get('has_more', False)}")
        assert len(data1["abstracts"]) == 5, "Page 1 should have 5 items"
        assert len(data2["abstracts"]) == 5, "Page 2 should have 5 items"
        # Compare IDs (could be abstract_id or publication_id)
        id1 = data1["abstracts"][0].get("abstract_id") or data1["abstracts"][0].get("publication_id")
        id2 = data2["abstracts"][0].get("abstract_id") or data2["abstracts"][0].get("publication_id")
        assert id1 != id2, "Pages should have different items"
        
        # Test 6: Filtering by cancer type
        print("\n6. Testing filtering by cancer_type...")
        response = await client.get("/api/analytics/data?cancer_type=Cutaneous%20Melanoma&limit=10")
        assert response.status_code == 200
        data = response.json()
        print(f"   ✅ Status: {response.status_code}")
        print(f"   ✅ Filtered abstracts: {data['total_abstracts']}")
        
        # Test 7: Chart data endpoint
        print("\n7. Testing /api/analytics/chart-data endpoint...")
        response = await client.get("/api/analytics/chart-data?target_metric=MEDIAN_OS&limit=10")
        assert response.status_code == 200
        chart_data = response.json()
        print(f"   ✅ Status: {response.status_code}")
        print(f"   ✅ Treatment groups: {len(chart_data.get('treatmentGroups', []))}")
        print(f"   ✅ Summary abstracts: {chart_data.get('summary', {}).get('totalAbstracts', 0)}")
        
        # Test 8: Verify data integrity
        print("\n8. Testing data integrity...")
        response = await client.get("/api/analytics/data?limit=1")
        data = response.json()
        if data["abstracts"]:
            abstract = data["abstracts"][0]
            assert "arm_results" in abstract, "Abstract should have arm_results"
            assert len(abstract["arm_results"]) > 0, "Abstract should have at least one arm"
            print(f"   ✅ Abstract ID: {abstract.get('abstract_id') or abstract.get('publication_id')}")
            print(f"   ✅ Arms: {len(abstract['arm_results'])}")
            print(f"   ✅ Attributes extracted: {abstract.get('total_attributes_extracted', 0)}")
        
        print("\n" + "=" * 60)
        print("✅ All SQLite API tests passed!")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_sqlite_api())
