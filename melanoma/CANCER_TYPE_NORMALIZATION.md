# Cancer Type Normalization

## Overview

The bionocular pipeline uses **8 standard cancer type categories**. All cancer type names from various sources (clinical trials, publications, etc.) are automatically normalized to these standard categories.

## Standard Cancer Types

The 8 standard cancer types used in the pipeline are:

1. **Basal Cell Carcinoma**
2. **Cutaneous Squamous Cell Carcinoma**
3. **Cutaneous melanoma** (with important subcategories - see below)
4. **Uveal Melanoma**
5. **Merkel Cell Carcinoma**
6. **Acral Melanoma**
7. **Mucosal Melanoma**
8. **Cutaneous melanoma with Brain/CNS metastasis**

## Important Subcategories

While these subcategories roll up to "Cutaneous melanoma" for reporting purposes, they are **preserved as distinct types** in the approval status system because they have different treatment approvals:

- **Resected Cutaneous Melanoma** (adjuvant setting)
- **Unresectable Cutaneous Melanoma** (advanced/metastatic setting)

### Why Preserve These Subcategories?

The same therapy can have different approval status based on disease setting:

| Therapy | Resected (Adjuvant) | Unresectable (Advanced) |
|---------|---------------------|-------------------------|
| Nivolumab | ✅ Approved | ✅ Approved |
| Pembrolizumab | ✅ Approved | ✅ Approved |
| Ipilimumab + Nivolumab | ❌ Non-approved | ✅ Approved |
| Dabrafenib + Trametinib | ✅ Approved | ✅ Approved |

If we collapsed these to just "Cutaneous melanoma," we would lose critical clinical distinctions.

## Normalization Examples

### Exact Matches
- `"Basal Cell Carcinoma"` → `"Basal Cell Carcinoma"`
- `"Merkel Cell Carcinoma"` → `"Merkel Cell Carcinoma"`
- `"Uveal Melanoma"` → `"Uveal Melanoma"`

### Subcategory Preservation
- `"Resected Cutaneous Melanoma"` → `"Resected Cutaneous Melanoma"` ✅ Preserved
- `"Unresectable Cutaneous Melanoma"` → `"Unresectable Cutaneous Melanoma"` ✅ Preserved
- `"Unresectable or Metastatic Melanoma"` → `"Unresectable Cutaneous Melanoma"`

### Parent Category Normalization
- `"Advanced Cutaneous Melanoma"` → `"Cutaneous melanoma"`
- `"Metastatic Melanoma"` → `"Cutaneous melanoma"`
- `"Advanced Melanoma"` → `"Cutaneous melanoma"`
- `"Melanoma"` → `"Cutaneous melanoma"`

### Brain/CNS Metastasis
- `"Cutaneous melanoma with Brain metastasis"` → `"Cutaneous melanoma with Brain/CNS metastasis"`
- `"Cutaneous Melanoma with CNS metastasis"` → `"Cutaneous melanoma with Brain/CNS metastasis"`
- `"Melanoma with Brain metastasis"` → `"Cutaneous melanoma with Brain/CNS metastasis"`

### Case Insensitive
- `"basal cell carcinoma"` → `"Basal Cell Carcinoma"`
- `"MERKEL CELL CARCINOMA"` → `"Merkel Cell Carcinoma"`
- `"unresectable cutaneous melanoma"` → `"Unresectable Cutaneous Melanoma"`

## Usage

### In Code

```python
from domain.cancer_type_normalizer import normalize_cancer_type

# Normalize a cancer type
normalized = normalize_cancer_type("Resected Cutaneous Melanoma")
print(normalized)  # "Resected Cutaneous Melanoma"

normalized = normalize_cancer_type("Advanced Melanoma")
print(normalized)  # "Cutaneous melanoma"

normalized = normalize_cancer_type("Melanoma with Brain metastasis")
print(normalized)  # "Cutaneous melanoma with Brain/CNS metastasis"

# Check if subcategory matches parent
from domain.cancer_type_normalizer import is_subcategory_match

match = is_subcategory_match(
    "Unresectable Cutaneous Melanoma",
    "Cutaneous melanoma"
)
print(match)  # True (for reporting purposes, they're related)
```

### In Classifier

The therapy classifier automatically normalizes cancer types:

```python
from domain.therapy_classifier import TherapyClassifier

classifier = TherapyClassifier()

# These all work correctly with automatic normalization
status1 = classifier.classify_arm(
    "Pembrolizumab",
    cancer_type="Unresectable Cutaneous Melanoma"
)  # APPROVED

status2 = classifier.classify_arm(
    "Pembrolizumab",
    cancer_type="unresectable cutaneous melanoma"  # lowercase
)  # APPROVED (same result)

status3 = classifier.classify_arm(
    "Ipilimumab + Nivolumab",
    cancer_type="Resected Cutaneous Melanoma"
)  # INVESTIGATIONAL (not approved in adjuvant setting)

status4 = classifier.classify_arm(
    "Ipilimumab + Nivolumab",
    cancer_type="Unresectable Cutaneous Melanoma"
)  # APPROVED (approved in advanced setting)
```

## Normalization Statistics

After regenerating the approval status configuration, you'll see which raw cancer type names were normalized:

```
Cutaneous melanoma:
  ← Advanced Cutaneous Melanoma
  ← Advanced Melanoma
  ← Melanoma
  ← Metastatic Melanoma
  ← ...

Resected Cutaneous Melanoma:
  ← Resected Cutaneous Melanoma  (preserved)

Unresectable Cutaneous Melanoma:
  ← Unresectable Cutaneous Melanoma  (preserved)
  ← Unresectable or Metastatic Melanoma
  ← Unresectable or metastatic cutaneous melanoma

Cutaneous melanoma with Brain/CNS metastasis:
  ← Cutaneous melanoma with Brain metastasis
  ← Cutaneous Melanoma with CNS metastasis
  ← Melanoma with Brain metastasis
```

## Files

- **Normalizer**: `melanoma/src/domain/cancer_type_normalizer.py`
- **Usage in Classifier**: `melanoma/src/domain/therapy_classifier.py`
- **Test Suite**: `melanoma/tests/test_therapy_classifier.py`
- **Config Generator**: `melanoma/scripts/generate_approval_yaml.py`

## Regenerating Configuration

When approval status data changes, regenerate the configuration with normalized cancer types:

```bash
cd melanoma
python3 scripts/generate_approval_yaml.py
python3 tests/test_therapy_classifier.py  # Verify
```

The generator will show normalization statistics for all cancer types encountered.
