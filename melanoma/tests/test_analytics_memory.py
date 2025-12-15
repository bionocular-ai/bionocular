#!/usr/bin/env python3
"""
Test script to monitor memory usage when accessing the analytics endpoint.
This helps identify memory spikes when loading large JSON files.
"""

import os
import sys
import time

import psutil
import requests


def get_process_memory(pid: int) -> dict:
    """Get memory usage for a process."""
    try:
        process = psutil.Process(pid)
        memory_info = process.memory_info()
        return {
            "rss_mb": memory_info.rss / (1024 * 1024),
            "vms_mb": memory_info.vms / (1024 * 1024),
            "percent": process.memory_percent(),
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def monitor_analytics_endpoint(base_url: str = "http://localhost:8000"):
    """Monitor memory usage when calling the analytics endpoint."""
    print("=" * 70)
    print("Analytics Endpoint Memory Test")
    print("=" * 70)
    print()

    # Find backend process
    backend_pid = None
    try:
        result = os.popen("lsof -ti:8000").read().strip()
        if result:
            backend_pid = int(result.split("\n")[0])
            print(f"Found backend process: PID {backend_pid}")
        else:
            print("❌ Backend not running on port 8000")
            return
    except Exception as e:
        print(f"❌ Error finding backend process: {e}")
        return

    # Get baseline memory
    print("\n1. Getting baseline memory usage...")
    baseline = get_process_memory(backend_pid)
    if baseline:
        print(f"   Baseline: {baseline['rss_mb']:.2f} MB ({baseline['percent']:.2f}%)")

    time.sleep(1)

    # Call analytics endpoint
    print("\n2. Calling /api/analytics/data endpoint...")
    start_time = time.time()

    try:
        response = requests.get(f"{base_url}/api/analytics/data", timeout=60)
        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success! Response time: {elapsed:.2f}s")
            print(f"   Total abstracts: {data.get('total_abstracts', 0)}")
            print(f"   Total arms: {data.get('total_arms', 0)}")

            # Estimate response size
            import json

            response_size_mb = len(json.dumps(data)) / (1024 * 1024)
            print(f"   Response size: ~{response_size_mb:.2f} MB")
        else:
            print(f"   ❌ Error: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
        return

    # Get peak memory during request
    print("\n3. Checking memory after request...")
    time.sleep(0.5)  # Wait a bit for memory to stabilize
    peak = get_process_memory(backend_pid)
    if peak and baseline:
        memory_increase = peak["rss_mb"] - baseline["rss_mb"]
        print(f"   Peak memory: {peak['rss_mb']:.2f} MB ({peak['percent']:.2f}%)")
        print(f"   Memory increase: {memory_increase:.2f} MB")

        if memory_increase > 100:
            print("   ⚠️  WARNING: Large memory increase detected!")

    # Check resource endpoint
    print("\n4. Checking /api/resources endpoint...")
    try:
        resource_response = requests.get(f"{base_url}/api/resources", timeout=5)
        if resource_response.status_code == 200:
            resources = resource_response.json()
            proc_info = resources.get("process", {})
            print(f"   Process memory: {proc_info.get('memory_mb', 'N/A')} MB")
            print(f"   CPU usage: {proc_info.get('cpu_percent', 'N/A')}%")
            print(f"   Child processes: {proc_info.get('num_children', 0)}")
        else:
            print(f"   ⚠️  Resource endpoint returned: {resource_response.status_code}")
    except Exception as e:
        print(f"   ⚠️  Could not check resource endpoint: {e}")

    print("\n" + "=" * 70)
    print("Test complete!")
    print("=" * 70)


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    monitor_analytics_endpoint(base_url)
