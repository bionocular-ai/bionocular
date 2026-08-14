"""Parser for ClinicalTrials.gov v2 API JSON into Supabase `clinical_trials` rows.

Returns a flat dict whose keys match every column in the production
`clinical_trials` table. Lifted from scripts/upload_to_supabase.py so the
sync pipeline and the legacy uploader share a single source of truth.
"""

import logging
from typing import Any, Optional

from .cancer_type_derivation import derive_cancer_types

logger = logging.getLogger(__name__)


# Canonical skin-cancer type names (must match values written to clinical_trials.cancer_type[]).
CANCER_TYPE_MAP: dict[str, str] = {
    # Melanoma variants
    "cutaneous-melanoma": "Cutaneous Melanoma",
    "cutaneous melanoma": "Cutaneous Melanoma",
    "cutaneous-melanoma-with-brain-cns-metastasis": "Cutaneous Melanoma with Brain/CNS Metastasis",
    "cutaneous melanoma with brain/cns metastasis": "Cutaneous Melanoma with Brain/CNS Metastasis",
    "uveal-melanoma": "Uveal Melanoma",
    "uveal melanoma": "Uveal Melanoma",
    "acral-melanoma": "Acral Melanoma",
    "acral melanoma": "Acral Melanoma",
    "mucosal-melanoma": "Mucosal Melanoma",
    "mucosal melanoma": "Mucosal Melanoma",
    # Non-Melanoma Skin Cancer (NMSC)
    "cutaneous-squamous-cell-carcinoma": "Cutaneous Squamous Cell Carcinoma",
    "cutaneous squamous cell carcinoma": "Cutaneous Squamous Cell Carcinoma",
    "cscc": "Cutaneous Squamous Cell Carcinoma",
    "basal-cell-carcinoma": "Basal Cell Carcinoma",
    "basal cell carcinoma": "Basal Cell Carcinoma",
    "bcc": "Basal Cell Carcinoma",
    "merkel-cell-carcinoma": "Merkel Cell Carcinoma",
    "merkel cell carcinoma": "Merkel Cell Carcinoma",
    "mcc": "Merkel Cell Carcinoma",
}

# Multi-indication trial labels that map to multiple canonical cancer types.
# `None` value = intentionally excluded (too broad to be useful as a tag).
MULTI_CANCER_TYPE_MAP: dict[str, Optional[list[str]]] = {
    "uveal / mucosal / acral melanoma": [
        "Uveal Melanoma",
        "Mucosal Melanoma",
        "Acral Melanoma",
    ],
    "basal cell / merkel cell / cutaneous squamous cell carcinoma": [
        "Basal Cell Carcinoma",
        "Merkel Cell Carcinoma",
        "Cutaneous Squamous Cell Carcinoma",
    ],
    "advanced non-uveal melanoma": ["Mucosal Melanoma", "Acral Melanoma"],
    "advanced solid tumors": None,
    "metastatic solid tumors": None,
}


def normalize_cancer_type(raw_type: Optional[str]) -> list[str]:
    """Map a raw cancer-type label to canonical names. Empty list if unmappable."""
    if not raw_type:
        return []
    clean = str(raw_type).lower().strip()

    if clean in MULTI_CANCER_TYPE_MAP:
        result = MULTI_CANCER_TYPE_MAP[clean]
        return result if result else []

    single = CANCER_TYPE_MAP.get(clean)
    return [single] if single else []


def parse_age_to_years(age_str: Optional[str]) -> Optional[float]:
    """Convert strings like '18 Years' or '6 Months' to a float number of years."""
    if not age_str:
        return None
    age_str = age_str.lower().strip()
    try:
        val = float(age_str.split()[0])
    except (ValueError, IndexError):
        return None
    if "month" in age_str:
        return val / 12.0
    if "week" in age_str:
        return val / 52.14
    if "day" in age_str:
        return val / 365.25
    return val


def sanitize_date(date_str: Optional[str]) -> Optional[str]:
    """Coerce ClinicalTrials.gov partial dates into Postgres-friendly YYYY-MM-DD."""
    if not date_str:
        return None
    if len(date_str) == 10:
        return date_str
    if len(date_str) == 7 and "-" in date_str:
        return f"{date_str}-01"
    if len(date_str) == 4 and date_str.isdigit():
        return f"{date_str}-01-01"
    return date_str


def extract_processed_trial(
    raw_json: dict[str, Any],
    nct_id: str,
    cancer_types_map: dict[str, list[str]],
) -> dict[str, Any]:
    """Flatten a v2 API trial JSON into a row matching the `clinical_trials` schema."""
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
    oversight_mod = protocol.get("oversightModule", {})
    references_mod = raw_json.get("referencesModule", {})

    design_info = design_mod.get("designInfo", {})

    min_age_raw = elig_mod.get("minimumAge")
    max_age_raw = elig_mod.get("maximumAge")

    conditions = cond_mod.get("conditions", [])
    keywords = cond_mod.get("keywords", [])

    # Shadow columns. `cancer_type` still carries the query-derived value so nothing
    # user-facing moves; the derived label is validated and promoted separately.
    derived = derive_cancer_types(conditions, keywords)

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
        "has_results": raw_json.get("hasResults", False),
        "has_expanded_access": status_mod.get("expandedAccessInfo", {}).get(
            "hasExpandedAccess", False
        ),
        "allocation": design_info.get("allocation"),
        "intervention_model": design_info.get("interventionModel"),
        "masking": design_info.get("maskingInfo", {}).get("masking"),
        "oversight_has_dmc": oversight_mod.get("oversightHasDmc", False),
        "is_fda_regulated_drug": oversight_mod.get("isFdaRegulatedDrug", False),
        "is_fda_regulated_device": oversight_mod.get("isFdaRegulatedDevice", False),
        "start_date": sanitize_date(status_mod.get("startDateStruct", {}).get("date")),
        "primary_completion_date": sanitize_date(
            status_mod.get("primaryCompletionDateStruct", {}).get("date")
        ),
        "completion_date": sanitize_date(
            status_mod.get("completionDateStruct", {}).get("date")
        ),
        "first_posted_date": sanitize_date(
            status_mod.get("studyFirstPostDateStruct", {}).get("date")
        ),
        "last_update_posted_date": sanitize_date(
            status_mod.get("lastUpdatePostDateStruct", {}).get("date")
        ),
        "lead_sponsor_name": sponsor_mod.get("leadSponsor", {}).get("name"),
        "lead_sponsor_class": sponsor_mod.get("leadSponsor", {}).get("class"),
        "investigator_name": sponsor_mod.get("responsibleParty", {}).get(
            "investigatorFullName"
        ),
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
        "cancer_type": cancer_types_map.get(nct_id, []),
        "cancer_type_derived": derived.buckets,
        "cancer_type_evidence": derived.evidence,
        "is_basket": derived.is_basket,
        "melanoma_unspecified": derived.melanoma_unspecified,
        "conditions": conditions,
        "keywords": keywords,
        "locations": loc_mod.get("locations", []),
        "interventions": arms_mod.get("interventions", []),
        "arm_groups": arms_mod.get("armGroups", []),
        "primary_outcomes": out_mod.get("primaryOutcomes", []),
        "secondary_outcomes": out_mod.get("secondaryOutcomes", []),
        "study_references": references_mod.get("references", []),
    }
