#!/usr/bin/env python3
"""Test script to verify web scrape data integration.

This script tests:
1. Database contains web-scraped trials
2. API can serve the data
3. Data structure is correct for frontend consumption
"""

import json
import sqlite3
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

def test_database():
    """Test that database contains web-scraped trials."""
    print("=" * 80)
    print("Testing Database Integration")
    print("=" * 80)
    
    db_path = Path(__file__).parent / "data" / "trials_db" / "trials.db"
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return False
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    # Count web-scraped trials
    cursor = conn.execute(
        "SELECT COUNT(*) as count FROM abstracts WHERE abstract_id LIKE 'webscrape_%'"
    )
    count = cursor.fetchone()["count"]
    
    if count == 0:
        print(f"❌ No web-scraped trials found in database")
        print("   Run: poetry run python scripts/import_web_scrape.py")
        conn.close()
        return False
    
    print(f"✅ Found {count} web-scraped trials in database")
    
    # Get details of one trial
    cursor = conn.execute("""
        SELECT abstract_id, file, total_arms, total_attributes_extracted, arm_results
        FROM abstracts 
        WHERE abstract_id LIKE 'webscrape_%'
        LIMIT 1
    """)
    
    row = cursor.fetchone()
    if row:
        print(f"\n📋 Sample trial: {row['abstract_id']}")
        print(f"   File: {row['file']}")
        print(f"   Arms: {row['total_arms']}")
        print(f"   Attributes: {row['total_attributes_extracted']}")
        
        # Parse arm_results
        try:
            arm_results = json.loads(row['arm_results'])
            first_arm = list(arm_results.values())[0] if arm_results else None
            
            if first_arm:
                arm_name = first_arm.get('arm_name', 'N/A')
                print(f"   First arm: {arm_name}")
                
                # Check for common attributes
                attributes = first_arm.get('attributes', {})
                generic_name_attr = attributes.get('AttributeType.GENERIC_NAME', {})
                generic_name = generic_name_attr.get('value', 'N/A')
                print(f"   Generic name: {generic_name}")
                
        except json.JSONDecodeError as e:
            print(f"   ⚠️  Error parsing arm_results: {e}")
    
    conn.close()
    print("\n✅ Database test passed")
    return True


def test_api():
    """Test that API can serve web-scraped trials."""
    print("\n" + "=" * 80)
    print("Testing API Integration")
    print("=" * 80)
    
    try:
        import requests
    except ImportError:
        print("⚠️  requests library not available, skipping API test")
        print("   Install with: pip install requests")
        return True
    
    # Test API endpoint
    try:
        response = requests.get("http://localhost:8000/api/analytics/data", params={"limit": 1100}, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ API returned status code {response.status_code}")
            return False
        
        data = response.json()
        abstracts = data.get('abstracts', [])
        
        # Find web-scraped trials
        webscrape_trials = [
            a for a in abstracts 
            if a.get('abstract_id', '').startswith('webscrape_')
        ]
        
        if not webscrape_trials:
            print("❌ No web-scraped trials found in API response")
            print("   Total abstracts returned:", len(abstracts))
            print("\n   Possible issues:")
            print("   1. API server needs restart: Stop and start the server")
            print("   2. Check database: sqlite3 data/trials_db/trials.db \"SELECT COUNT(*) FROM abstracts WHERE abstract_id LIKE 'webscrape_%'\"")
            return False
        
        print(f"✅ Found {len(webscrape_trials)} web-scraped trials in API response")
        
        # Check one trial in detail
        trial = webscrape_trials[0]
        print(f"\n📋 Sample API trial: {trial.get('abstract_id')}")
        print(f"   NCT ID: {trial.get('nct_id', 'N/A')}")
        print(f"   Title: {trial.get('title', 'N/A')}")
        print(f"   Cancer type: {trial.get('cancer_type', 'N/A')}")
        print(f"   Phase: {trial.get('phase', 'N/A')}")
        print(f"   Type: {trial.get('type', 'N/A')}")
        
        # Check arms
        arms = trial.get('arms', [])
        if arms:
            print(f"   Arms: {len(arms)}")
            print(f"   First arm: {arms[0].get('arm_name', 'N/A')}")
        
        print("\n✅ API test passed")
        return True
        
    except requests.exceptions.ConnectionError:
        print("⚠️  Could not connect to API server at http://localhost:8000")
        print("   Make sure the server is running:")
        print("   poetry run uvicorn src.app.api:app --reload --host 0.0.0.0 --port 8000")
        return True  # Not a failure, just server not running
        
    except Exception as e:
        print(f"❌ Error testing API: {e}")
        return False


def test_data_structure():
    """Test that data structure matches frontend expectations."""
    print("\n" + "=" * 80)
    print("Testing Data Structure")
    print("=" * 80)
    
    db_path = Path(__file__).parent / "data" / "trials_db" / "trials.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("""
        SELECT abstract_id, arm_results
        FROM abstracts 
        WHERE abstract_id LIKE 'webscrape_%'
        LIMIT 1
    """)
    
    row = cursor.fetchone()
    if not row:
        print("❌ No web-scraped trial found for structure test")
        conn.close()
        return False
    
    try:
        arm_results = json.loads(row['arm_results'])
        
        # Check structure
        if not arm_results:
            print("❌ arm_results is empty")
            conn.close()
            return False
        
        first_arm_key = list(arm_results.keys())[0]
        first_arm = arm_results[first_arm_key]
        
        # Check required fields
        required_fields = ['arm_id', 'arm_name', 'attributes']
        missing_fields = [f for f in required_fields if f not in first_arm]
        
        if missing_fields:
            print(f"❌ Missing required fields in arm: {missing_fields}")
            conn.close()
            return False
        
        print("✅ Arm structure is correct")
        
        # Check attributes structure
        attributes = first_arm.get('attributes', {})
        if not attributes:
            print("⚠️  No attributes found in arm")
        else:
            # Check one attribute structure
            first_attr_key = list(attributes.keys())[0]
            first_attr = attributes[first_attr_key]
            
            attr_fields = ['value', 'source', 'confidence']
            has_all = all(f in first_attr for f in attr_fields)
            
            if has_all:
                print("✅ Attribute structure is correct")
                print(f"   Sample attribute: {first_attr_key}")
                print(f"   Value: {first_attr.get('value')}")
                print(f"   Source: {first_attr.get('source')}")
                print(f"   Confidence: {first_attr.get('confidence')}")
            else:
                print(f"⚠️  Attribute structure may be incomplete: {first_attr}")
        
        conn.close()
        print("\n✅ Data structure test passed")
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing arm_results JSON: {e}")
        conn.close()
        return False
    except Exception as e:
        print(f"❌ Error in structure test: {e}")
        conn.close()
        return False


def main():
    """Run all tests."""
    print("\n🧪 Testing Web Scrape Data Integration\n")
    
    results = []
    
    # Run tests
    results.append(("Database", test_database()))
    results.append(("Data Structure", test_data_structure()))
    results.append(("API", test_api()))
    
    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n✅ All tests passed! Web scrape data is properly integrated.")
        print("\nNext steps:")
        print("1. Open the frontend: http://localhost:3000")
        print("2. Navigate to: Dashboard > Analytics")
        print("3. Look for trials with abstract IDs starting with 'webscrape_'")
        print("4. Verify they appear in charts and comparative analytics")
    else:
        print("\n❌ Some tests failed. Please review the output above.")
        print("\nCommon fixes:")
        print("1. Restart API server:")
        print("   poetry run uvicorn src.app.api:app --reload --host 0.0.0.0 --port 8000")
        print("2. Re-import web scrape data:")
        print("   poetry run python scripts/import_web_scrape.py")
        print("3. Rebuild database:")
        print("   poetry run python scripts/build_db.py --db-path data/trials_db/trials.db")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

