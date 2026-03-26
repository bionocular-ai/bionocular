import os
import sys
import json
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    sys.exit(1)

supabase: Client = create_client(url, key)

base_dir = "data/deployed"

# Canonical Skin Cancer Types
CANCER_TYPE_MAP = {
    # Melanoma Variants
    "cutaneous-melanoma": "Cutaneous Melanoma",
    "cutaneous melanoma": "Cutaneous Melanoma",
    "cutaneous-melanoma-with-brain-cns-metastasis": "Cutaneous Melanoma (Brain/CNS Metastases)",
    "cutaneous melanoma with brain/cns metastasis": "Cutaneous Melanoma (Brain/CNS Metastases)",
    "uveal-melanoma": "Uveal Melanoma",
    "uveal melanoma": "Uveal Melanoma",
    "acral-melanoma": "Acral Melanoma",
    "acral melanoma": "Acral Melanoma",
    "mucosal-melanoma": "Mucosal Melanoma",
    "mucosal melanoma": "Mucosal Melanoma",
    
    # Non-Melanoma Skin Cancer (NMSC)
    "cutaneous-squamous-cell-carcinoma": "Cutaneous Squamous Cell Carcinoma (cSCC)",
    "cutaneous squamous cell carcinoma": "Cutaneous Squamous Cell Carcinoma (cSCC)",
    "cscc": "Cutaneous Squamous Cell Carcinoma (cSCC)",
    "basal-cell-carcinoma": "Basal Cell Carcinoma (BCC)",
    "basal cell carcinoma": "Basal Cell Carcinoma (BCC)",
    "bcc": "Basal Cell Carcinoma (BCC)",
    "merkel-cell-carcinoma": "Merkel Cell Carcinoma (MCC)",
    "merkel cell carcinoma": "Merkel Cell Carcinoma (MCC)",
    "mcc": "Merkel Cell Carcinoma (MCC)"
}

# Multi-indication trials that map to multiple canonical cancer types
MULTI_CANCER_TYPE_MAP = {
    "uveal / mucosal / acral melanoma": ["Uveal Melanoma", "Mucosal Melanoma", "Acral Melanoma"],
    "basal cell / merkel cell / cutaneous squamous cell carcinoma": [
        "Basal Cell Carcinoma", "Merkel Cell Carcinoma", "Cutaneous Squamous Cell Carcinoma"
    ],
    "advanced non-uveal melanoma": ["Mucosal Melanoma", "Acral Melanoma"],
    "advanced solid tumors": None,  # Too broad — intentionally excluded
    "metastatic solid tumors": None,  # Too broad — intentionally excluded
}

def normalize_cancer_type(raw_type) -> list:
    """Maps a raw cancer type string to a list of canonical cancer type(s).
    Returns an empty list if the type cannot be confidently mapped."""
    if not raw_type: return []
    clean = str(raw_type).lower().strip()
    
    # Check multi-value map first
    if clean in MULTI_CANCER_TYPE_MAP:
        result = MULTI_CANCER_TYPE_MAP[clean]
        return result if result else []  # Excluded types return empty
    
    # Single-value map
    single = CANCER_TYPE_MAP.get(clean)
    return [single] if single else []

import sqlite3

def parse_age_to_years(age_str):
    """Converts strings like '18 Years' or '6 Months' into a numeric year representation."""
    if not age_str: return None
    age_str = age_str.lower().strip()
    try:
        val = float(age_str.split()[0])
        if 'month' in age_str: return val / 12.0
        if 'week' in age_str: return val / 52.14
        if 'day' in age_str: return val / 365.25
        return val
    except Exception:
        return None

def sanitize_date(date_str):
    """Ensures date strings are in YYYY-MM-DD format for Postgres.
    If the API provides YYYY-MM, we append -01.
    """
    if not date_str: return None
    # If already YYYY-MM-DD
    if len(date_str) == 10: return date_str
    # If YYYY-MM
    if len(date_str) == 7 and "-" in date_str:
        return f"{date_str}-01"
    # If just YYYY
    if len(date_str) == 4 and date_str.isdigit():
        return f"{date_str}-01-01"
    return date_str

def extract_processed_trial(raw_json, nct_id, cancer_types_map):
    """Extract and flatten complex Trial JSON into SQL-friendly columns."""
    protocol = raw_json.get("protocolSection", {})
    id_mod = protocol.get("identificationModule", {})
    status_mod = protocol.get("statusModule", {})
    design_mod = protocol.get("designModule", {})
    sponsor_mod = protocol.get("sponsorCollaboratorsModule", {})
    desc_mod = protocol.get("descriptionModule", {})
    cond_mod = protocol.get("conditionsModule", {})
    elig_mod = protocol.get("eligibilityModule", {})
    arms_mod = protocol.get("armsInterventionsModule", {})
    out_mod = protocol.get("outcomesModule", {})
    loc_mod = protocol.get("contactsLocationsModule", {})
    
    has_results = raw_json.get("hasResults", False)
    expanded_access = status_mod.get("expandedAccessInfo", {}).get("hasExpandedAccess", False)
    has_dmc = protocol.get("oversightModule", {}).get("oversightHasDmc", False)
    is_fda_drug = protocol.get("oversightModule", {}).get("isFdaRegulatedDrug", False)
    is_fda_device = protocol.get("oversightModule", {}).get("isFdaRegulatedDevice", False)
    design_info = design_mod.get("designInfo", {})
    references_mod = raw_json.get("referencesModule", {})
    
    min_age_raw = elig_mod.get("minimumAge")
    max_age_raw = elig_mod.get("maximumAge")
    
    return {
        "nct_id": nct_id,
        "brief_title": id_mod.get("briefTitle"),
        "official_title": id_mod.get("officialTitle"),
        "acronym": id_mod.get("acronym"),
        "overall_status": status_mod.get("overallStatus"),
        "study_type": design_mod.get("studyType"),
        "primary_purpose": design_info.get("primaryPurpose"),
        "phases": design_mod.get("phases", []),
        "enrollment_count": design_mod.get("enrollmentInfo", {}).get("count"),
        "has_results": has_results,
        "has_expanded_access": expanded_access,
        
        "allocation": design_info.get("allocation"),
        "intervention_model": design_info.get("interventionModel"),
        "masking": design_info.get("maskingInfo", {}).get("masking"),
        "oversight_has_dmc": has_dmc,
        "is_fda_regulated_drug": is_fda_drug,
        "is_fda_regulated_device": is_fda_device,
        
        "start_date": sanitize_date(status_mod.get("startDateStruct", {}).get("date")),
        "primary_completion_date": sanitize_date(status_mod.get("primaryCompletionDateStruct", {}).get("date")),
        "completion_date": sanitize_date(status_mod.get("completionDateStruct", {}).get("date")),
        "first_posted_date": sanitize_date(status_mod.get("studyFirstPostDateStruct", {}).get("date")),
        "last_update_posted_date": sanitize_date(status_mod.get("lastUpdatePostDateStruct", {}).get("date")),
        
        "lead_sponsor_name": sponsor_mod.get("leadSponsor", {}).get("name"),
        "lead_sponsor_class": sponsor_mod.get("leadSponsor", {}).get("class"),
        "investigator_name": sponsor_mod.get("responsibleParty", {}).get("investigatorFullName"),
        
        "minimum_age": min_age_raw,
        "maximum_age": max_age_raw,
        "min_age_years": parse_age_to_years(min_age_raw),
        "max_age_years": parse_age_to_years(max_age_raw),
        "std_ages": elig_mod.get("stdAges", []),
        "sex": elig_mod.get("sex"),
        "healthy_volunteers": elig_mod.get("healthyVolunteers"),
        
        "brief_summary": desc_mod.get("briefSummary"),
        "detailed_description": desc_mod.get("detailedDescription"),
        "eligibility_criteria": elig_mod.get("eligibilityCriteria"),
        
        # New natively-array typed columns
        "cancer_type": cancer_types_map.get(nct_id, []),
        "conditions": cond_mod.get("conditions", []),
        "keywords": cond_mod.get("keywords", []),
        
        # JSONB arrays
        "locations": loc_mod.get("locations", []),
        "interventions": arms_mod.get("interventions", []),
        "arm_groups": arms_mod.get("armGroups", []),
        "primary_outcomes": out_mod.get("primaryOutcomes", []),
        "secondary_outcomes": out_mod.get("secondaryOutcomes", []),
        "study_references": references_mod.get("references", []),
    }

def upload_clinical_trials():
    print("Uploading clinical_trials_cache and clinical_trials...")
    path = os.path.join(base_dir, "clinical_trials_api_seed.json")
    if not os.path.exists(path):
        print(f"Skipping: {path} not found")
        return
    
    # 1. Load the SQLite cancer_types_map
    cancer_types_map = {}
    sqlite_db_path = "data/trials_db/trials.db"
    if os.path.exists(sqlite_db_path):
        print("Extracting cancer_type mappings from local trials.db SQLite database...")
        conn = sqlite3.connect(sqlite_db_path)
        cur = conn.cursor()
        try:
            cur.execute("SELECT nct_number, cancer_type_tag FROM api_discovery")
            for row in cur.fetchall():
                nct = row[0]
                tag = row[1]
                if nct not in cancer_types_map:
                    cancer_types_map[nct] = []
                # Normalize the tag from SQLite before adding to map
                normalized_tags = normalize_cancer_type(tag)
                for normalized_tag in normalized_tags:
                    if normalized_tag not in cancer_types_map[nct]:
                        cancer_types_map[nct].append(normalized_tag)
        except Exception as e:
            print(f"Error reading api_discovery: {e}")
        finally:
            conn.close()
    
    with open(path, 'r') as f:
        data = json.load(f)
        
    cache = data.get("clinical_trials_cache", [])
    if not cache:
        print("No cache found")
        return
        
    batch_size = 20
    total = len(cache)
    print(f"Found {total} trials to process. Uploading in batches of {batch_size}...")
    
    for i in range(0, total, batch_size):
        batch = cache[i:i+batch_size]
        
        cache_batch = []
        processed_batch = []
        
        for item in batch:
            raw_str = item.get("api_response_json", "{}")
            nct_id = item.get("nct_number")
            try:
                raw_json = json.loads(raw_str) if isinstance(raw_str, str) else dict(raw_str)
            except:
                raw_json = {}
                
            # Use the mapped cancer_types for trial_outcomes records
            cancer_types = cancer_types_map.get(nct_id, [])
            
            processed_sql_record = extract_processed_trial(raw_json, nct_id, cancer_types_map)
            processed_batch.append(processed_sql_record)
            
        try:
            # Upsert ONLY into processed table (clinical_trials_cache is already in Supabase)
            supabase.table("clinical_trials").upsert(processed_batch).execute()
            print(f"  ✓ Inserted batch {i//batch_size + 1} / {(total + batch_size - 1) // batch_size} into clinical_trials")
        except Exception as e:
            print(f"  ✗ Error inserting batch {i//batch_size + 1}: {e}")

def upload_trial_landscape():
    print("Uploading trial_landscape...")
    path = os.path.join(base_dir, "trial_categorization_seed.json")
    if not os.path.exists(path): return
    
    with open(path, 'r') as f:
        data = json.load(f)
        
    batch_size = 500
    for i in range(0, len(data), batch_size):
        batch = data[i:i+batch_size]
        try:
            supabase.table("trial_landscape").upsert(batch).execute()
        except Exception as e:
            print(f"  Error: {e}")
    print(f"  Inserted {len(data)} trial landscape records")

# Comprehensive mapping from AttributeType key to SQL column name
ATTRIBUTE_MAPPING = {
    # Core Identification
    "CANCER_TYPE": "cancer_type",
    "SPONSORS": "sponsors",
    "LINE_OF_TREATMENT": "line_of_treatment",
    "GENERIC_NAME": "generic_name",
    "BRAND_NAME": "brand_name",
    "DOSAGE": "dosage",
    "TYPE_OF_DOSING": "type_of_dosing",
    "MECHANISM_OF_ACTION": "mechanism_of_action",
    "TARGET_PROTEIN": "target_protein",
    "TYPE_OF_THERAPY": "type_of_therapy",
    "SUB_THERAPY": "sub_therapy",
    "MEDIAN_AGE": "median_age",
    "NUMBER_OF_PATIENTS": "num_patients",

    # Efficacy: PFS
    "MEDIAN_PFS": "median_pfs",
    "MEDIAN_FOLLOWUP_PFS": "pfs_followup_months",
    "P_VALUE_PFS": "p_value_pfs",
    "HR_PFS": "hr_pfs",
    "PFS_RATE_6M": "pfs_rate_6m",
    "PFS_RATE_9M": "pfs_rate_9m",
    "PFS_RATE_12M": "pfs_rate_12m",
    "PFS_RATE_18M": "pfs_rate_18m",
    "PFS_RATE_24M": "pfs_rate_24m",
    "PFS_RATE_36M": "pfs_rate_36m",
    "PFS_RATE_48M": "pfs_rate_48m",

    # Efficacy: OS
    "MEDIAN_OS": "median_os",
    "MEDIAN_FOLLOWUP_OS": "os_followup_months",
    "P_VALUE_OS": "p_value_os",
    "HR_OS": "hr_os",
    "OS_RATE_6M": "os_rate_6m",
    "OS_RATE_9M": "os_rate_9m",
    "OS_RATE_12M": "os_rate_12m",
    "OS_RATE_18M": "os_rate_18m",
    "OS_RATE_24M": "os_rate_24m",
    "OS_RATE_36M": "os_rate_36m",
    "OS_RATE_48M": "os_rate_48m",

    # Efficacy: Other Survival
    "EFS": "efs",
    "P_VALUE_EFS": "p_value_efs",
    "HR_EFS": "hr_efs",
    "RFS": "rfs",
    "P_VALUE_RFS": "p_value_rfs",
    "LENGTH_RFS": "rfs_followup_months",
    "HR_RFS": "hr_rfs",
    "MFS": "mfs",
    "LENGTH_MFS": "mfs_followup_months",
    "HR_MFS": "hr_mfs",

    # Efficacy: Response
    "OBJECTIVE_RESPONSE_RATE": "orr",
    "COMPLETE_RESPONSE": "cr",
    "PATHOLOGICAL_COMPLETE_RESPONSE": "pcr",
    "COMPLETE_METABOLIC_RESPONSE": "cmr",
    "DISEASE_CONTROL_RATE": "dcr",
    "CLINICAL_BENEFIT_RATE": "cbr",
    "MEDIAN_DOR": "median_dor",
    "DOR_RATE": "dor_rate",
    "TTR": "ttr",
    "TTP": "ttp",
    "TTNT": "ttnt",
    "TTF": "ttf",

    # Safety: General
    "AE": "ae_pct",
    "GRADE_3_PLUS_AE": "grade_3_plus_ae_pct",
    "AE_LEADING_TO_DISCONTINUATION": "ae_leading_to_discontinuation_pct",
    "SERIOUS_AE": "serious_ae_pct",
    "IMMUNE_RELATED_AE": "immune_related_ae_pct",
    "SERIOUS_IMMUNE_RELATED_AE": "serious_ir_ae_pct",
    "AE_LED_TO_DEATH": "ae_death_pct",

    # Safety: TRAE
    "TRAE": "trae_pct",
    "GRADE_3_PLUS_TRAE": "grade_3_plus_trae_pct",
    "GRADE_3_TRAE": "grade_3_trae_pct",
    "GRADE_4_TRAE": "grade_4_trae_pct",
    "GRADE_5_TRAE": "grade_5_trae_pct",
    "TRAE_LEADING_TO_DISCONTINUATION": "trae_discontinuation_pct",
    "TRAE_LEADING_TO_DEATH": "trae_death_pct",
    "TRAE_IMMUNE_RELATED": "trae_ir_ae_pct",
    "SERIOUS_TRAE": "serious_trae_pct",

    # Safety: TEAE
    "TEAE": "teae_pct",
    "GRADE_3_PLUS_TEAE": "grade_3_plus_teae_pct",
    "GRADE_3_TEAE": "grade_3_teae_pct",
    "GRADE_4_TEAE": "grade_4_teae_pct",
    "GRADE_5_TEAE": "grade_5_teae_pct",
    "TEAE_LEADING_TO_DISCONTINUATION": "teae_discontinuation_pct",
    "TEAE_LEADING_TO_DEATH": "teae_death_pct",
    "TEAE_IMMUNE_RELATED": "teae_ir_ae_pct",
    "SERIOUS_TEAE": "serious_teae_pct",

    # Safety: Syndromes
    "CRS": "crs_pct",
    "WBC_DECREASED": "wbc_decreased_pct",

    # Safety: Specific Grade 3+ AEs
    "GRADE_3_PLUS_AE_IMMUNE_RELATED": "grade_3_plus_ae_ir_ae",
    "GRADE_3_PLUS_AE_CRS": "grade_3_plus_ae_crs",
    "GRADE_3_PLUS_AE_THROMBOCYTOPENIA": "grade_3_plus_ae_thrombocytopenia",
    "GRADE_3_PLUS_AE_NEUTROPENIA": "grade_3_plus_ae_neutropenia",
    "GRADE_3_PLUS_AE_LEUKOPENIA": "grade_3_plus_ae_leukopenia",
    "GRADE_3_PLUS_AE_NAUSEA": "grade_3_plus_ae_nausea",
    "GRADE_3_PLUS_AE_ANEMIA": "grade_3_plus_ae_anemia",
    "GRADE_3_PLUS_AE_DIARRHEA": "grade_3_plus_ae_diarrhea",
    "GRADE_3_PLUS_AE_COLITIS": "grade_3_plus_ae_colitis",
    "GRADE_3_PLUS_AE_HYPERGLYCEMIA": "grade_3_plus_ae_hyperglycemia",
    "GRADE_3_PLUS_AE_NEUTROPHIL_COUNT_DECREASED": "grade_3_plus_ae_neutrophil_count_decreased",
    "GRADE_3_PLUS_AE_DYSPNEA": "grade_3_plus_ae_dyspnea",
    "GRADE_3_PLUS_AE_PYREXIA": "grade_3_plus_ae_pyrexia",
    "GRADE_3_PLUS_AE_BLEEDING": "grade_3_plus_ae_bleeding",
    "GRADE_3_PLUS_AE_PRURITUS": "grade_3_plus_ae_pruritus",
    "GRADE_3_PLUS_AE_RASH": "grade_3_plus_ae_rash",
    "GRADE_3_PLUS_AE_PNEUMONIA": "grade_3_plus_ae_pneumonia",
    "GRADE_3_PLUS_AE_THYROIDITIS": "grade_3_plus_ae_thyroiditis",
    "GRADE_3_PLUS_AE_HYPOPHYSITIS": "grade_3_plus_ae_hypophysitis",
    "GRADE_3_PLUS_AE_HEPATITIS": "grade_3_plus_ae_hepatitis",
    "GRADE_3_PLUS_AE_PNEUMONITIS": "grade_3_plus_ae_pneumonitis",
    "GRADE_3_PLUS_AE_ALANINE_AMINOTRANSFERASE": "grade_3_plus_ae_alt_increased",
    "GRADE_3_PLUS_AE_WBC_DECREASED": "grade_3_plus_ae_wbc_decreased",

    # Safety: Specific Grade 3+ TRAEs
    "GRADE_3_PLUS_TRAE_IMMUNE_RELATED": "grade_3_plus_trae_ir_ae",
    "GRADE_3_PLUS_TRAE_CRS": "grade_3_plus_trae_crs",
    "GRADE_3_PLUS_TRAE_THROMBOCYTOPENIA": "grade_3_plus_trae_thrombocytopenia",
    "GRADE_3_PLUS_TRAE_NEUTROPENIA": "grade_3_plus_trae_neutropenia",
    "GRADE_3_PLUS_TRAE_LEUKOPENIA": "grade_3_plus_trae_leukopenia",
    "GRADE_3_PLUS_TRAE_NAUSEA": "grade_3_plus_trae_nausea",
    "GRADE_3_PLUS_TRAE_ANEMIA": "grade_3_plus_trae_anemia",
    "GRADE_3_PLUS_TRAE_DIARRHEA": "grade_3_plus_trae_diarrhea",
    "GRADE_3_PLUS_TRAE_COLITIS": "grade_3_plus_trae_colitis",
    "GRADE_3_PLUS_TRAE_HYPERGLYCEMIA": "grade_3_plus_trae_hyperglycemia",
    "GRADE_3_PLUS_TRAE_NEUTROPHIL_COUNT_DECREASED": "grade_3_plus_trae_neutrophil_count_decreased",
    "GRADE_3_PLUS_TRAE_DYSPNEA": "grade_3_plus_trae_dyspnea",
    "GRADE_3_PLUS_TRAE_PYREXIA": "grade_3_plus_trae_pyrexia",
    "GRADE_3_PLUS_TRAE_BLEEDING": "grade_3_plus_trae_bleeding",
    "GRADE_3_PLUS_TRAE_PRURITUS": "grade_3_plus_trae_pruritus",
    "GRADE_3_PLUS_TRAE_RASH": "grade_3_plus_trae_rash",
    "GRADE_3_PLUS_TRAE_PNEUMONIA": "grade_3_plus_trae_pneumonia",
    "GRADE_3_PLUS_TRAE_THYROIDITIS": "grade_3_plus_trae_thyroiditis",
    "GRADE_3_PLUS_TRAE_HYPOPHYSITIS": "grade_3_plus_trae_hypophysitis",
    "GRADE_3_PLUS_TRAE_HEPATITIS": "grade_3_plus_trae_hepatitis",
    "GRADE_3_PLUS_TRAE_PNEUMONITIS": "grade_3_plus_trae_pneumonitis",
    "GRADE_3_PLUS_TRAE_ALANINE_AMINOTRANSFERASE": "grade_3_plus_trae_alt_increased",
    "GRADE_3_PLUS_TRAE_WBC_DECREASED": "grade_3_plus_trae_wbc_decreased",

    # Safety: Specific Grade 3+ TEAEs
    "GRADE_3_PLUS_TEAE_IMMUNE_RELATED": "grade_3_plus_teae_ir_ae",
    "GRADE_3_PLUS_TEAE_CRS": "grade_3_plus_teae_crs",
    "GRADE_3_PLUS_TEAE_THROMBOCYTOPENIA": "grade_3_plus_teae_thrombocytopenia",
    "GRADE_3_PLUS_TEAE_NEUTROPENIA": "grade_3_plus_teae_neutropenia",
    "GRADE_3_PLUS_TEAE_LEUKOPENIA": "grade_3_plus_teae_leukopenia",
    "GRADE_3_PLUS_TEAE_NAUSEA": "grade_3_plus_teae_nausea",
    "GRADE_3_PLUS_TEAE_ANEMIA": "grade_3_plus_teae_anemia",
    "GRADE_3_PLUS_TEAE_DIARRHEA": "grade_3_plus_teae_diarrhea",
    "GRADE_3_PLUS_TEAE_COLITIS": "grade_3_plus_teae_colitis",
    "GRADE_3_PLUS_TEAE_HYPERGLYCEMIA": "grade_3_plus_teae_hyperglycemia",
    "GRADE_3_PLUS_TEAE_NEUTROPHIL_COUNT_DECREASED": "grade_3_plus_teae_neutrophil_count_decreased",
    "GRADE_3_PLUS_TEAE_DYSPNEA": "grade_3_plus_teae_dyspnea",
    "GRADE_3_PLUS_TEAE_PYREXIA": "grade_3_plus_teae_pyrexia",
    "GRADE_3_PLUS_TEAE_BLEEDING": "grade_3_plus_teae_bleeding",
    "GRADE_3_PLUS_TEAE_PRURITUS": "grade_3_plus_teae_pruritus",
    "GRADE_3_PLUS_TEAE_RASH": "grade_3_plus_teae_rash",
    "GRADE_3_PLUS_TEAE_PNEUMONIA": "grade_3_plus_teae_pneumonia",
    "GRADE_3_PLUS_TEAE_THYROIDITIS": "grade_3_plus_teae_thyroiditis",
    "GRADE_3_PLUS_TEAE_HYPOPHYSITIS": "grade_3_plus_teae_hypophysitis",
    "GRADE_3_PLUS_TEAE_HEPATITIS": "grade_3_plus_teae_hepatitis",
    "GRADE_3_PLUS_TEAE_PNEUMONITIS": "grade_3_plus_teae_pneumonitis",
    "GRADE_3_PLUS_TEAE_ALANINE_AMINOTRANSFERASE": "grade_3_plus_teae_alt_increased",
    "GRADE_3_PLUS_TEAE_WBC_DECREASED": "grade_3_plus_teae_wbc_decreased",
}

def get_attr_value(attrs, key, default=None, is_numeric=False):
    """Helper to extract a value from the attributes dict, handling numeric conversion simply."""
    # Try multiple key formats
    candidates = [f"AttributeType.{key}", key, key.lower(), key.upper()]
    val_obj = {}
    for c in candidates:
        if c in attrs:
            val_obj = attrs[c]
            break
            
    val = val_obj.get("value")
    # Handle common empty/non-numeric clinical strings
    if val in [None, "Not found", "", "NR", "N/A", "Not reached", "Not available"]:
        return default
    if is_numeric:
        try:
            return float(val)
        except:
            return default
    return val

def upload_trial_outcomes():
    print("Uploading trial_outcomes (Deeply Flattened)...")
    files = [f for f in os.listdir(base_dir) if f.endswith('.json') and any(x in f for x in ['ASCO', 'ESMO', 'Publications', 'web_scrape'])]
    
    # Sort order: ASCO -> ESMO -> Publication -> Webscrape
    def sort_key(f):
        if 'ASCO' in f: return 1
        if 'ESMO' in f: return 2
        if 'Publications' in f: return 3
        if 'web_scrape' in f: return 4
        return 5
    files.sort(key=sort_key)
    
    for file in files:
        path = os.path.join(base_dir, file)
        source_name = file.replace(".json", "")
        source_type = 'webscrape' if 'web_scrape' in file else 'abstract'
        if 'Publications' in file: source_type = 'publication'
        
        with open(path, 'r') as f:
            try:
                data = json.load(f)
                trials_list = []
                if isinstance(data, dict):
                    trials_list = data.get('trials', []) or data.get('abstracts', []) or data.get('publications', [])
                elif isinstance(data, list):
                    trials_list = data
                
                mapped_arms = []
                for trial in trials_list:
                    # Logic for trial IDs
                    raw_id = trial.get("trial_id") or trial.get("abstract_id") or trial.get("publication_id") or trial.get("id", "unknown")
                    nct_id = trial.get("nct_id") or (raw_id if str(raw_id).startswith("NCT") else None)
                    
                    # Publication & Arm specific Logic
                    arm_results = trial.get("arm_results", {})
                    first_arm_key = next(iter(arm_results.keys())) if arm_results else None
                    first_arm_attrs = arm_results[first_arm_key].get("attributes", {}) if first_arm_key else {}
                    
                    # Robust NCT ID extraction from attributes if still missing
                    if not nct_id:
                        # Case-insensitive search through all keys for common NCT patterns
                        for k, v in first_arm_attrs.items():
                            clean_k = k.lower().replace("attributetype.", "")
                            if clean_k in ["nct_number", "nct_id", "nct"]:
                                nct_id = v.get("value")
                                if nct_id == "Not found": nct_id = None
                                if nct_id: break
                    
                    if source_type == 'publication':
                        actual_source_name = raw_id # Publication ID (Batch ID)
                        # Specific logic for publication_id column matching user request
                        pub_id_value = first_arm_attrs.get("AttributeType.PUBLICATION_NAME", {}).get("value") or first_arm_attrs.get("PUBLICATION_NAME", {}).get("value")
                    else:
                        actual_source_name = source_name
                        pub_id_value = None
                    
                    arm_results = trial.get("arm_results", {})
                    if not arm_results: continue
                    
                    for arm_key, arm_data in arm_results.items():
                        arm_id = arm_data.get("arm_id", arm_key)
                        attrs = arm_data.get("attributes", {})
                        
                        pk = f"{source_type}_{raw_id}_{arm_id}".replace("/", "_").replace(" ", "_")
                        
                        # Build the record using the massive mapping dictionary
                        record = {
                            "id": pk,
                            "source_type": source_type,
                            "source_name": actual_source_name,
                            "abstract_id": str(raw_id) if source_type == 'abstract' else None,
                            "publication_id": pub_id_value,
                            "source_url": trial.get("source_url"),
                            "nct_id": nct_id,
                            "arm_id": arm_id,
                            "arm_name": arm_data.get("arm_name"),
                            "confidence": trial.get("overall_confidence", 0.0),
                            "all_attributes": attrs
                        }
                        
                        # Pre-normalize all attributes for this trial to handle various naming conventions
                        norm_attrs = {}
                        for k, v in attrs.items():
                            clean_k = k.lower().replace("attributetype.", "").replace("_", "")
                            norm_attrs[clean_k] = v

                        # Fill in the flattened columns
                        is_nr_list = []
                        known_strings = [
                            'id', 'source_type', 'source_name', 'abstract_id', 'publication_id', 
                            'source_url', 'nct_id', 'arm_id', 'arm_name', 'cancer_type', 'sponsors', 
                            'line_of_treatment', 'generic_name', 'brand_name', 'dosage', 
                            'type_of_dosing', 'mechanism_of_action', 'target_protein', 
                            'type_of_therapy', 'sub_therapy', 'is_nr', 'all_attributes', 'created_at'
                        ]
                        
                        for attr_key, col_name in ATTRIBUTE_MAPPING.items():
                            is_num = col_name not in known_strings
                            
                            # Use normalized lookup
                            clean_target = attr_key.lower().replace("_", "")
                            val_obj = norm_attrs.get(clean_target, {})
                            
                            val = val_obj.get("value")
                            # Check for "NR" specifically to add to the array
                            if str(val).upper() in ["NR", "NOT REACHED", "NOTREACHED"]:
                                is_nr_list.append(col_name)
                                val = None
                            elif val in [None, "Not found", "", "N/A", "Not available"]:
                                val = None
                            
                            # Perform numeric conversion if needed
                            if is_num and val is not None:
                                try:
                                    val = float(val)
                                    if col_name == 'num_patients':
                                        val = int(val)
                                except:
                                    val = None
                            
                            record[col_name] = val

                        # cancer_type: normalize from raw attr, store as TEXT[]
                        raw_ct = record.get('cancer_type')
                        if isinstance(raw_ct, str):
                            record['cancer_type'] = normalize_cancer_type(raw_ct)
                        elif not isinstance(raw_ct, list):
                            record['cancer_type'] = []

                        record["is_nr"] = is_nr_list if is_nr_list else None
                        mapped_arms.append(record)
                
                if mapped_arms:
                    b_size = 50 # Smaller batch due to 100+ columns
                    for i in range(0, len(mapped_arms), b_size):
                        batch = mapped_arms[i:i+b_size]
                        supabase.table("trial_outcomes").upsert(batch).execute()
                    print(f"  ✓ Inserted {len(mapped_arms)} deeply flattened arms from {file}")
                    
            except Exception as e:
                print(f"  ✗ Error processing {file}: {e}")

def upload_news_feed():
    print("Uploading news_feed...")
    path = os.path.join(base_dir, "live_ticker.json")
    if not os.path.exists(path): return
    
    with open(path, 'r') as f:
        data = json.load(f)
        
    mapped_data = []
    for raw_cancer_type, content in data.items():
        # Standardize the cancer type name using the global map
        cancer_type = normalize_cancer_type(raw_cancer_type)
        
        articles = content.get('articles', []) if isinstance(content, dict) else content
        if not isinstance(articles, list): continue
        for art in articles:
            mapped_data.append({
                "cancer_type": cancer_type,
                "title": art.get("title", ""),
                "date": art.get("date", ""),
                "url": art.get("url", ""),
                "nct_id": art.get("nct_id", "")
            })
            
    try:
        supabase.table("news_feed").upsert(mapped_data).execute()
        print(f"  Inserted {len(mapped_data)} news feed records")
    except Exception as e:
        print(f"  Error: {e}")

if __name__ == "__main__":
    print("Starting trial_outcomes ONLY upload to Supabase...")
    upload_trial_outcomes()
    print("Migration complete!")
