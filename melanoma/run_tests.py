#!/usr/bin/env python3
"""
Test Runner for Embedding and Indexing Modules

Runs all tests in the correct order:
1. Unit tests for individual components
2. Integration tests for component interactions
3. End-to-end tests for complete pipeline

Usage:
    python run_tests.py
"""

import subprocess
import sys
import time
from pathlib import Path


def run_command(command: str, description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"🧪 {description}")
    print(f"{'='*60}")
    print(f"Running: {command}")
    print()
    
    start_time = time.time()
    result = subprocess.run(command.split(), capture_output=True, text=True)
    end_time = time.time()
    
    duration = end_time - start_time
    
    if result.returncode == 0:
        print(f"✅ {description} - PASSED ({duration:.2f}s)")
        if result.stdout:
            print("Output:")
            print(result.stdout)
        return True
    else:
        print(f"❌ {description} - FAILED ({duration:.2f}s)")
        if result.stdout:
            print("Output:")
            print(result.stdout)
        if result.stderr:
            print("Error:")
            print(result.stderr)
        return False


def main():
    """Run all tests in sequence."""
    print("🚀 Starting Embedding and Indexing Test Suite")
    print("=" * 80)
    
    # Check if we're in the right directory
    if not Path("src").exists():
        print("❌ Error: Please run this script from the melanoma project root directory")
        sys.exit(1)
    
    # Define test commands in order
    test_commands = [
        {
            "command": "pytest tests/test_embeddings.py -v",
            "description": "Embedding Module Tests"
        },
        {
            "command": "pytest tests/test_indexing.py -v", 
            "description": "Indexing Module Tests (Unit + Integration)"
        }
    ]
    
    # Run tests
    passed_tests = 0
    total_tests = len(test_commands)
    
    for test in test_commands:
        success = run_command(test["command"], test["description"])
        if success:
            passed_tests += 1
        else:
            print(f"\n❌ Test failed: {test['description']}")
            print("Stopping test execution due to failure.")
            break
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 Test Summary")
    print(f"{'='*80}")
    print(f"Tests passed: {passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed!")
        print("\n✅ Embedding and Indexing modules are working correctly!")
        return 0
    else:
        print("❌ Some tests failed!")
        print("\n🔧 Please check the test output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
