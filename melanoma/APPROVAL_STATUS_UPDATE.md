# Therapy Approval Status Update

## Overview

Updated the therapy approval status classification system to use correct arm names and indication-specific approval status from `melanoma/data/deployed/approval_status.txt`. All cancer types are automatically normalized to the **8 standard categories** used in the bionocular pipeline.

## Problem

The previous logic in `melanoma/resources/therapy_approval_status.yaml` had:
- **Incorrect arm names**: Generic therapy names that didn't match actual clinical trial arm names
- **Missing indication context**: Same therapy categorized as approved/investigational globally, without considering specific cancer type indications
- **Inaccurate classifications**: Many therapies incorrectly classified due to lack of context

## Solution

### 1. New Data Source
- **Source**: `melanoma/data/deployed/approval_status.txt`
- **Contains**: 1,738 rows with exact arm names, cancer types, and approval status
  - 706 approved entries
  - 1,018 non-approved entries
  - 196 unique approved arm names
  - 603 unique non-approved arm names

### 2. Generated Configuration Files

Created auto-generation script: `melanoma/scripts/generate_approval_yaml.py`

**Generates:**
- `melanoma/resources/therapy_approval_status.yaml` (for human readability)
- `melanoma/resources/therapy_approval_status.json` (for code usage, no PyYAML dependency)

**Structure:**
```json
{
  "approved_therapies": [
    {
      "arm_name": "Nivolumab",
      "cancer_types": [
        "Resected Cutaneous Melanoma",
        "Unresectable Cutaneous Melanoma"
      ]
    }
  ],
  "non_approved_therapies": [
    {
      "arm_name": "Placebo",
      "cancer_types": ["Resected Cutaneous Melanoma"]
    }
  ]
}
```

### 3. Updated Classifier Logic

**File**: `melanoma/src/domain/therapy_classifier.py`

**Key Changes:**
1. **Added `cancer_type` parameter** to `classify_arm()` method:
   ```python
   def classify_arm(
       self,
       arm_name: str,
       cancer_type: Optional[str] = None,  # NEW
       generic_name: Optional[str] = None,
       title: Optional[str] = None,
   ) -> TherapyStatus:
   ```

2. **Exact matching with indication**:
   - Looks up `(arm_name, cancer_type)` pairs for precise classification
   - Falls back to `arm_name` only if cancer type not provided
   - Maintains backward compatibility with legacy code

3. **New lookup structure**:
   ```python
   self.exact_matches = {
       ("nivolumab", "resected cutaneous melanoma"): TherapyStatus.APPROVED,
       ("nivolumab", "unresectable cutaneous melanoma"): TherapyStatus.APPROVED,
       ("ipilimumab + nivolumab", "resected cutaneous melanoma"): TherapyStatus.INVESTIGATIONAL,
       # ... thousands more entries
   }
   ```

### 4. Cancer Type Normalization

**File**: `melanoma/src/domain/cancer_type_normalizer.py`

All cancer types are normalized to the **8 standard pipeline categories**:
1. Basal Cell Carcinoma
2. Cutaneous Squamous Cell Carcinoma
3. Cutaneous melanoma
4. Uveal Melanoma
5. Merkel Cell Carcinoma
6. Acral Melanoma
7. Mucosal Melanoma
8. Cutaneous melanoma with Brain/CNS metastasis

**Important subcategories preserved** (not collapsed to parent):
- **Resected Cutaneous Melanoma** (adjuvant setting)
- **Unresectable Cutaneous Melanoma** (advanced/metastatic setting)

These are preserved because the same therapy can have different approval status:
- `Ipilimumab + Nivolumab` + Resected → ❌ Non-approved
- `Ipilimumab + Nivolumab` + Unresectable → ✅ Approved

**Example normalizations:**
- `"Advanced Melanoma"` → `"Cutaneous melanoma"`
- `"Metastatic Melanoma"` → `"Cutaneous melanoma"`
- `"Resected Cutaneous Melanoma"` → `"Resected Cutaneous Melanoma"` (preserved)
- `"Cutaneous melanoma with Brain metastasis"` → `"Cutaneous melanoma with Brain/CNS metastasis"`

See **`CANCER_TYPE_NORMALIZATION.md`** for complete details.

### 5. Test Suite

**File**: `melanoma/tests/test_therapy_classifier.py`

Verifies classifier accuracy with known examples:
- ✅ **All 15 test cases pass**
- Tests approved therapies with specific indications
- Tests non-approved therapies
- Tests same drug with different approval status based on indication
- Tests cancer type normalization (case-insensitive, variations)

## Key Insights

### Indication-Specific Approval
The same therapy can have **different approval status** depending on indication:

| Arm Name | Cancer Type | Status |
|----------|-------------|--------|
| Pembrolizumab | Unresectable Cutaneous Melanoma | ✅ **Approved** |
| Pembrolizumab | *(no cancer type)* | ❌ **Non-approved** |
| Ipilimumab + Nivolumab | Unresectable Cutaneous Melanoma | ✅ **Approved** |
| Ipilimumab + Nivolumab | Resected Cutaneous Melanoma | ❌ **Non-approved** |

### Exact Arm Names Matter
- "Nivolumab" ≠ "Nivolumab + Ipilimumab"
- "Cemiplimab 350 mg Q3W" (approved) ≠ "Cemiplimab 3 mg/kg Q2W" (non-approved)
- Dosing regimens affect approval status

## Usage

### Regenerate Configuration Files
```bash
cd melanoma
python3 scripts/generate_approval_yaml.py
```

This reads `melanoma/data/deployed/approval_status.txt` and regenerates:
- `melanoma/resources/therapy_approval_status.yaml`
- `melanoma/resources/therapy_approval_status.json`

### Run Tests
```bash
cd melanoma
python3 tests/test_therapy_classifier.py
```

### Use in Code
```python
from domain.therapy_classifier import TherapyClassifier

classifier = TherapyClassifier()

# With cancer type (recommended for accuracy)
status = classifier.classify_arm(
    arm_name="Nivolumab",
    cancer_type="Resected Cutaneous Melanoma"
)
# Returns: TherapyStatus.APPROVED

# Without cancer type (less accurate)
status = classifier.classify_arm(arm_name="Nivolumab")
# Returns: TherapyStatus.APPROVED (partial match)
```

## Files Modified

1. **New Scripts**:
   - `melanoma/scripts/generate_approval_yaml.py` - Auto-generates config files with cancer type normalization

2. **New Domain Logic**:
   - `melanoma/src/domain/cancer_type_normalizer.py` - Normalizes cancer types to 8 standard categories

3. **New Tests**:
   - `melanoma/tests/test_therapy_classifier.py` - Unit tests for therapy classifier

4. **Updated Code**:
   - `melanoma/src/domain/therapy_classifier.py` - Updated classifier logic with cancer type normalization

5. **Generated/Regenerated**:
   - `melanoma/resources/therapy_approval_status.yaml` - Human-readable config with normalized types
   - `melanoma/resources/therapy_approval_status.json` - Machine-readable config with normalized types

6. **Documentation**:
   - `melanoma/APPROVAL_STATUS_UPDATE.md` - This file
   - `melanoma/CANCER_TYPE_NORMALIZATION.md` - Complete normalization guide

7. **Data Source** (unchanged, used as reference):
   - `melanoma/data/deployed/approval_status.txt` - Source of truth

## Validation

✅ All test cases pass  
✅ Backward compatible with existing code (cancer_type is optional)  
✅ No external dependencies (uses JSON instead of requiring PyYAML)  
✅ Automatic generation from source of truth  
✅ Handles 1,738 arm+indication combinations  

## Next Steps

When updating approval status data:
1. Update `melanoma/data/deployed/approval_status.txt`
2. Run `python3 scripts/generate_approval_yaml.py`
3. Run `python3 scripts/test_classifier.py` to verify
4. Configuration files are automatically regenerated
