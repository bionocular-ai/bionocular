import json
import os
import sys

# Add current directory to path
sys.path.append(os.path.dirname(__file__))
from upload_to_supabase import ATTRIBUTE_MAPPING

def test_normalization():
    base_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'deployed')
    
    # Test case: ESMO_2025 where keys are lowercase and underscores exist
    test_file = 'ESMO_2025.json'
    path = os.path.join(base_dir, test_file)
    
    print("=" * 80)
    print("TESTING UNIVERSAL NORMALIZATION (Dry Run)")
    print("=" * 80)
    
    if not os.path.exists(path):
        print(f"Skipping {test_file} (not found)")
        return
        
    with open(path, 'r') as f:
        data = json.load(f)
        
    abstracts = data.get('abstracts', [])
    target = next((t for t in abstracts if t.get('abstract_id') == 'ESMO_2025_1685TiP'), abstracts[0])
    
    arm_results = target.get("arm_results", {})
    first_arm_key = next(iter(arm_results.keys()))
    attrs = arm_results[first_arm_key].get("attributes", {})
    
    # NORMALIZATION LOGIC from upload_to_supabase.py
    norm_attrs = {}
    for k, v in attrs.items():
        clean_k = k.lower().replace("attributetype.", "").replace("_", "")
        norm_attrs[clean_k] = v
        
    # Test NCT_ID Extraction logic
    nct_id = None
    for k, v in attrs.items():
        clean_k = k.lower().replace("attributetype.", "")
        if clean_k in ["nct_number", "nct_id", "nct"]:
            nct_id = v.get("value")
            if nct_id == "Not found": nct_id = None
            if nct_id: break

    # Test clinical column logic
    target_pfs_key = "MEDIAN_PFS"
    clean_target = target_pfs_key.lower().replace("_", "")
    pfs_val = norm_attrs.get(clean_target, {}).get("value")

    print(f"Trial ID: {target.get('abstract_id')}")
    print(f"Extracted NCT ID: {nct_id}")
    print(f"Extracted Median PFS: {pfs_val}")
    
    if nct_id:
        print("SUCCESS: NCT ID captured despite lowercase key!")
    else:
        print("FAILURE: NCT ID missed.")

    if pfs_val:
        print("SUCCESS: Clinical attribute captured through normalization!")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    test_normalization()
