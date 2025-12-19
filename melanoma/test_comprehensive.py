#!/usr/bin/env python3
"""Comprehensive test script for analytics optimizations."""

import asyncio
import os
import sys
import time
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

import httpx
from httpx import ASGITransport
import psutil
import subprocess

# Set environment variables before importing app
os.environ["TRIALS_DATA_SOURCE"] = "sqlite"
db_path = Path(__file__).parent / "data" / "trials_db" / "trials.db"
os.environ["TRIALS_DB_PATH"] = str(db_path)

from src.app.api import app, get_trials_service


def get_memory_usage():
    """Get current process memory usage in MB."""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


async def test_response_times():
    """Test response times for different endpoints."""
    print("\n" + "=" * 60)
    print("Response Time Comparison")
    print("=" * 60)
    
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        tests = [
            ("Unfiltered (limit=100)", "/api/analytics/data?limit=100"),
            ("Filtered (publications, limit=100)", "/api/analytics/data?resource_type=publication&limit=100"),
            ("Filtered (conference, limit=100)", "/api/analytics/data?resource_type=conference&limit=100"),
            ("Chart data (MEDIAN_OS)", "/api/analytics/chart-data?target_metric=MEDIAN_OS"),
            ("Filtered + chart data", "/api/analytics/chart-data?target_metric=MEDIAN_OS&resource_type=publication"),
        ]
        
        results = []
        for name, endpoint in tests:
            times = []
            for _ in range(3):  # Run 3 times and average
                start = time.time()
                response = await client.get(endpoint)
                elapsed = (time.time() - start) * 1000  # Convert to ms
                times.append(elapsed)
                assert response.status_code == 200, f"Failed: {endpoint}"
            
            avg_time = sum(times) / len(times)
            results.append((name, avg_time, min(times), max(times)))
            print(f"  {name:40s} {avg_time:6.1f}ms (min: {min(times):.1f}ms, max: {max(times):.1f}ms)")
        
        return results


async def test_additional_filters():
    """Test additional filter types."""
    print("\n" + "=" * 60)
    print("Additional Filter Tests")
    print("=" * 60)
    
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Test therapy_type filter
        print("\n1. Testing therapy_type filter...")
        response = await client.get("/api/analytics/data?therapy_type=Immunotherapy&limit=10")
        assert response.status_code == 200
        data = response.json()
        print(f"   ✅ Immunotherapy: {data['total_abstracts']} abstracts")
        
        # Test funding_type filter
        print("\n2. Testing funding_type filter...")
        response = await client.get("/api/analytics/data?funding_type=industry&limit=10")
        assert response.status_code == 200
        data = response.json()
        industry_count = data['total_abstracts']
        print(f"   ✅ Industry-funded: {industry_count} abstracts")
        
        response = await client.get("/api/analytics/data?funding_type=non-industry&limit=10")
        assert response.status_code == 200
        data = response.json()
        non_industry_count = data['total_abstracts']
        print(f"   ✅ Non-industry-funded: {non_industry_count} abstracts")
        
        # Test has_metric filter
        print("\n3. Testing has_metric filter...")
        response = await client.get("/api/analytics/data?has_metric=MEDIAN_OS&limit=10")
        assert response.status_code == 200
        data = response.json()
        print(f"   ✅ Has MEDIAN_OS: {data['total_abstracts']} abstracts")
        
        # Test combined filters
        print("\n4. Testing combined filters...")
        response = await client.get("/api/analytics/data?resource_type=publication&therapy_type=Immunotherapy&funding_type=industry&limit=10")
        assert response.status_code == 200
        data = response.json()
        print(f"   ✅ Combined (publication + immunotherapy + industry): {data['total_abstracts']} abstracts")
        
        # Test with chart data
        print("\n5. Testing filters with chart-data endpoint...")
        response = await client.get("/api/analytics/chart-data?target_metric=MEDIAN_OS&resource_type=publication")
        assert response.status_code == 200
        chart_data = response.json()
        print(f"   ✅ Chart data with filter: {len(chart_data.get('treatmentGroups', []))} treatment groups")
        print(f"   ✅ Summary abstracts: {chart_data.get('summary', {}).get('totalAbstracts', 0)}")
        
        return {
            "therapy_type": True,
            "funding_type": {"industry": industry_count, "non_industry": non_industry_count},
            "has_metric": True,
            "combined": True,
            "chart_with_filters": True
        }


async def test_edge_cases():
    """Test edge cases."""
    print("\n" + "=" * 60)
    print("Edge Case Tests")
    print("=" * 60)
    
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Test invalid filter values
        print("\n1. Testing invalid filter values...")
        response = await client.get("/api/analytics/data?resource_type=invalid&limit=10")
        assert response.status_code == 200  # Should not error, just return empty/filtered results
        data = response.json()
        print(f"   ✅ Invalid resource_type handled gracefully: {data['total_abstracts']} results")
        
        # Test empty results
        print("\n2. Testing filter that returns no results...")
        response = await client.get("/api/analytics/data?cancer_type=NonexistentCancer&limit=10")
        assert response.status_code == 200
        data = response.json()
        print(f"   ✅ Empty results handled: {data['total_abstracts']} results, {len(data['abstracts'])} returned")
        
        # Test very large limit
        print("\n3. Testing very large limit...")
        response = await client.get("/api/analytics/data?limit=10000")
        assert response.status_code == 200
        data = response.json()
        print(f"   ✅ Large limit handled: {len(data['abstracts'])} returned (total: {data['total_abstracts']})")
        
        # Test negative skip
        print("\n4. Testing negative skip...")
        response = await client.get("/api/analytics/data?skip=-10&limit=10")
        assert response.status_code == 200  # Should default to 0
        data = response.json()
        print(f"   ✅ Negative skip handled: {len(data['abstracts'])} returned")
        
        # Test special characters
        print("\n5. Testing special characters in filter...")
        response = await client.get("/api/analytics/data?cancer_type=Cutaneous%20Melanoma&limit=10")
        assert response.status_code == 200
        data = response.json()
        print(f"   ✅ Special characters handled: {data['total_abstracts']} results")
        
        # Test missing parameters
        print("\n6. Testing missing parameters...")
        response = await client.get("/api/analytics/data")
        assert response.status_code == 200
        data = response.json()
        print(f"   ✅ Missing parameters handled: {data['total_abstracts']} total, {len(data['abstracts'])} returned")
        
        return True


def test_memory_comparison():
    """Test memory usage comparison (requires server restart)."""
    print("\n" + "=" * 60)
    print("Memory Usage Comparison")
    print("=" * 60)
    print("\n⚠️  Note: This test requires manual server restart with different data sources.")
    print("   Current test shows SQLite memory usage.")
    print("   To compare with JSON, restart server with TRIALS_DATA_SOURCE=json\n")
    
    # Get current memory (SQLite)
    service = get_trials_service()
    service_type = type(service).__name__
    
    # Load some data to simulate usage
    abstracts, total = service.get_all_trials(limit=100)
    
    memory_mb = get_memory_usage()
    print(f"Current service: {service_type}")
    print(f"Memory after loading 100 trials: {memory_mb:.2f} MB")
    print(f"Loaded {len(abstracts)} abstracts (total available: {total})")
    
    return {
        "service_type": service_type,
        "memory_mb": memory_mb,
        "trials_loaded": len(abstracts)
    }


async def run_all_tests():
    """Run all comprehensive tests."""
    print("=" * 60)
    print("Comprehensive Analytics Optimization Tests")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Memory comparison
    results["memory"] = test_memory_comparison()
    
    # Test 2: Response times
    results["response_times"] = await test_response_times()
    
    # Test 3: Additional filters
    results["filters"] = await test_additional_filters()
    
    # Test 4: Edge cases
    results["edge_cases"] = await test_edge_cases()
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"✅ Memory: {results['memory']['service_type']} - {results['memory']['memory_mb']:.2f} MB")
    print(f"✅ Response Times: {len(results['response_times'])} tests completed")
    print(f"✅ Filters: All filter types tested")
    print(f"✅ Edge Cases: All edge cases handled")
    
    return results


if __name__ == "__main__":
    asyncio.run(run_all_tests())
