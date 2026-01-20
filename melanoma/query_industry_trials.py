#!/usr/bin/env python3
"""Query Industry-sponsored trials from clinical_trials_api.db
   Only includes trials with INDUSTRY lead sponsor and cancer types from api_discovery table."""

import sqlite3
import json
import csv
from pathlib import Path
from typing import List, Dict, Set
import re

def normalize_cancer_type(condition: str) -> str:
    """Normalize condition name to match api_discovery cancer types."""
    condition_lower = condition.lower()
    
    # Mapping of common condition names to api_discovery cancer types
    mappings = {
        'cutaneous melanoma': 'Cutaneous melanoma',
        'melanoma': 'Cutaneous melanoma',  # Default to cutaneous if not specified
        'uveal melanoma': 'Uveal Melanoma',
        'ocular melanoma': 'Uveal Melanoma',
        'acral melanoma': 'Acral Melanoma',
        'mucosal melanoma': 'Mucosal Melanoma',
        'merkel cell carcinoma': 'Merkel Cell Carcinoma',
        'basal cell carcinoma': 'Basal Cell Carcinoma',
        'basal cell cancer': 'Basal Cell Carcinoma',
        'cutaneous squamous cell carcinoma': 'Cutaneous Squamous Cell Carcinoma',
        'squamous cell carcinoma of the skin': 'Cutaneous Squamous Cell Carcinoma',
        'squamous cell skin cancer': 'Cutaneous Squamous Cell Carcinoma',
    }
    
    # Check for exact matches first
    for key, value in mappings.items():
        if key in condition_lower:
            return value
    
    # Check for brain/CNS metastasis in melanoma
    if 'melanoma' in condition_lower and ('brain' in condition_lower or 'cns' in condition_lower or 'central nervous system' in condition_lower):
        return 'Cutaneous melanoma with Brain/CNS metastasis'
    
    return None

def get_api_discovery_cancer_types(db_path: str) -> Set[str]:
    """Get all unique cancer types from api_discovery table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT cancer_type_tag FROM api_discovery")
    cancer_types = {row[0] for row in cursor.fetchall()}
    conn.close()
    return cancer_types

def get_industry_trials(db_path: str, valid_cancer_types: Set[str]) -> List[Dict]:
    """Extract Industry-sponsored trials with company, cancer type, and NCT.
       Only includes trials where lead sponsor is INDUSTRY and cancer type is in api_discovery."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # First, get NCT numbers and their cancer types from api_discovery
    cursor.execute("""
        SELECT DISTINCT nct_number, cancer_type_tag 
        FROM api_discovery
    """)
    discovery_trials = {}
    for nct_number, cancer_type in cursor.fetchall():
        if nct_number not in discovery_trials:
            discovery_trials[nct_number] = set()
        if cancer_type in valid_cancer_types:
            discovery_trials[nct_number].add(cancer_type)
    
    print(f"Found {len(discovery_trials)} unique NCTs in api_discovery")
    
    # Get trials from cache that are in api_discovery
    nct_list = list(discovery_trials.keys())
    placeholders = ','.join(['?'] * len(nct_list))
    cursor.execute(f"""
        SELECT nct_number, api_response_json 
        FROM clinical_trials_cache 
        WHERE nct_number IN ({placeholders})
    """, nct_list)
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} trials in clinical_trials_cache matching api_discovery")
    
    industry_trials = []
    
    for nct_number, api_json_str in rows:
        try:
            api_data = json.loads(api_json_str)
            
            # Navigate to sponsor/collaborator info
            sponsor_module = api_data.get('protocolSection', {}).get('sponsorCollaboratorsModule', {})
            lead_sponsor = sponsor_module.get('leadSponsor', {})
            
            # ONLY include if lead sponsor is Industry (not collaborators)
            lead_sponsor_class = lead_sponsor.get('class', '')
            if lead_sponsor_class != 'INDUSTRY':
                continue
            
            company = lead_sponsor.get('name', '')
            if not company:
                continue
            
            # Filter by study status: "Not yet recruiting", "Recruiting", "Active, not recruiting"
            status_module = api_data.get('protocolSection', {}).get('statusModule', {})
            overall_status = status_module.get('overallStatus', '')
            last_known_status = status_module.get('lastKnownStatus', '')
            
            # Check if status matches any of the desired statuses
            valid_statuses = {'NOT_YET_RECRUITING', 'RECRUITING', 'ACTIVE_NOT_RECRUITING'}
            if overall_status not in valid_statuses and last_known_status not in valid_statuses:
                continue
            
            # Use cancer types from api_discovery (more accurate than parsing conditions)
            cancer_types = discovery_trials.get(nct_number, set())
            
            # Only add if we have matching cancer types
            if cancer_types:
                for cancer_type in cancer_types:
                    industry_trials.append({
                        'nct_id': nct_number,
                        'company': company,
                        'cancer_type': cancer_type,
                        'lead_sponsor': company,
                        'lead_sponsor_class': lead_sponsor_class,
                        'overall_status': overall_status,
                        'last_known_status': last_known_status,
                    })
        
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error processing {nct_number}: {e}")
            continue
    
    conn.close()
    return industry_trials

def main():
    db_path = Path(__file__).parent / 'data' / 'clinical_trial_api' / 'clinical_trial_api.db'
    
    if not db_path.exists():
        print(f"Database not found at: {db_path}")
        return
    
    # Get valid cancer types from api_discovery table
    print("Loading cancer types from api_discovery table...")
    valid_cancer_types = get_api_discovery_cancer_types(str(db_path))
    print(f"Found {len(valid_cancer_types)} cancer types in api_discovery:")
    for ct in sorted(valid_cancer_types):
        print(f"  - {ct}")
    
    print("\nQuerying Industry-sponsored trials (lead sponsor only)...")
    print("Filtering by status: NOT_YET_RECRUITING, RECRUITING, ACTIVE_NOT_RECRUITING")
    trials = get_industry_trials(str(db_path), valid_cancer_types)
    
    if not trials:
        print("No Industry-sponsored trials found.")
        return
    
    # Get unique combinations
    unique_trials = {}
    for trial in trials:
        key = (trial['nct_id'], trial['company'], trial['cancer_type'])
        if key not in unique_trials:
            unique_trials[key] = trial
    
    trials_list = list(unique_trials.values())
    
    # Sort by company, then cancer type, then NCT
    trials_list.sort(key=lambda x: (x['company'], x['cancer_type'], x['nct_id']))
    
    # Print summary
    print(f"\nFound {len(trials_list)} Industry-sponsored trial entries")
    print(f"Unique NCTs: {len(set(t['nct_id'] for t in trials_list))}")
    print(f"Unique Companies: {len(set(t['company'] for t in trials_list))}")
    print(f"Unique Cancer Types: {len(set(t['cancer_type'] for t in trials_list))}")
    
    # Print to console
    print("\n" + "="*120)
    print(f"{'NCT ID':<15} {'Company':<35} {'Cancer Type':<35} {'Status':<20}")
    print("="*120)
    for trial in trials_list:
        # Prefer last_known_status if overall_status is UNKNOWN or empty
        overall = trial.get('overall_status', '')
        last_known = trial.get('last_known_status', '')
        if overall in {'UNKNOWN', ''} and last_known:
            status = last_known
        else:
            status = overall or last_known or 'N/A'
        print(f"{trial['nct_id']:<15} {trial['company']:<35} {trial['cancer_type']:<35} {status:<20}")
    
    # Save to CSV
    csv_path = db_path.parent / 'industry_trials.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['nct_id', 'company', 'cancer_type', 'lead_sponsor', 'lead_sponsor_class', 'overall_status', 'last_known_status'])
        writer.writeheader()
        writer.writerows(trials_list)
    
    print(f"\n\nResults saved to: {csv_path}")
    
    # Print company summary
    print("\n" + "="*60)
    print("Company Summary (number of trials per company):")
    print("="*60)
    company_counts = {}
    for trial in trials_list:
        company = trial['company']
        company_counts[company] = company_counts.get(company, 0) + 1
    
    for company, count in sorted(company_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"{company:<50} {count:>5} trials")

if __name__ == '__main__':
    main()

