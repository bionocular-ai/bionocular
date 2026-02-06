# Approval Status Integration: Backend to Frontend

## Clean Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         DATA SOURCE                              │
│  melanoma/data/deployed/approval_status.txt (1,738 entries)     │
│  ↓ arm_name + cancer_type + approval_status                     │
└─────────────────────────────────────────────────────────────────┘
                                ↓
                    python3 scripts/generate_approval_yaml.py
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                     GENERATED CONFIGS                            │
│  ✓ data/deployed/therapy_approval_status.json (backend)         │
│  ✓ resources/therapy_approval_status.yaml (human reference)     │
│                                                                  │
│  995 arm+indication combinations with normalized cancer types   │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND (Python)                              │
│                                                                  │
│  ApprovalStatusService                                           │
│  ├─ Loads therapy_approval_status.json                          │
│  ├─ Uses TherapyClassifier (indication-specific logic)          │
│  ├─ Normalizes cancer types (8 standard categories)             │
│  └─ Returns: "Approved", "Investigational", "Control"           │
│                                                                  │
│  JSONTrialsService (enriches data)                               │
│  ├─ Loads trial JSON files                                      │
│  ├─ Calls ApprovalStatusService for each arm                    │
│  └─ Adds approval_status field to arm data                      │
└─────────────────────────────────────────────────────────────────┘
                                ↓
                         JSON Response
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                   FRONTEND (TypeScript/React)                    │
│                                                                  │
│  chart-transformers.ts                                           │
│  ├─ Receives trial data with approval_status from backend       │
│  ├─ Uses backend approval_status when available                 │
│  └─ Falls back to simple name matching (legacy)                 │
│                                                                  │
│  Components (display only)                                       │
│  ├─ BarChart.tsx: Shows ★ for approved therapies               │
│  ├─ BubbleChart.tsx: Colors by approval status                  │
│  └─ DivergingBarChart.tsx: Badge display                        │
└─────────────────────────────────────────────────────────────────┘
```

## File Organization

### Data
- **Source of truth**: `melanoma/data/deployed/approval_status.txt`
- **Backend config**: `melanoma/data/deployed/therapy_approval_status.json`
- **Human reference**: `melanoma/resources/therapy_approval_status.yaml`

### Code
**Backend:**
- `melanoma/src/domain/therapy_classifier.py` - Core classification logic
- `melanoma/src/domain/cancer_type_normalizer.py` - Cancer type normalization
- `melanoma/src/app/approval_status_service.py` - Service layer
- `melanoma/src/app/json_trials_service.py` - Data enrichment

**Frontend:**
- `web/src/lib/chart-transformers.ts` - Uses backend approval_status

**Scripts:**
- `melanoma/scripts/generate_approval_yaml.py` - Generates configs from source data

**Tests:**
- `melanoma/tests/test_therapy_classifier.py` - Unit tests for classifier
- `melanoma/tests/test_approval_status_service.py` - Service integration tests

## Data Flow Example

### 1. Backend Enrichment

```python
# JSONTrialsService automatically enriches arms with approval status
service = JSONTrialsService(enable_approval_status=True)  # Default

abstract = service.get_full_abstract_by_id("ASCO_2020_10000")

# Each arm now has approval_status field:
{
  "arm_results": {
    "arm_1": {
      "arm_name": "Pembrolizumab",
      "approval_status": "Approved",  # ← Added by ApprovalStatusService
      "attributes": {
        "AttributeType.CANCER_TYPE": {
          "value": "Resected Cutaneous Melanoma"
        }
      }
    }
  }
}
```

### 2. Frontend Consumption

```typescript
// chart-transformers.ts - Uses backend status when available
function getApprovalStatus(treatmentName: string, backendStatus?: string): ApprovalStatus {
  // Prefer backend status (indication-specific, accurate)
  if (backendStatus) {
    if (backendStatus.toLowerCase() === 'approved') return 'Approved';
    return 'Investigational';
  }
  
  // Fallback to simple name matching for old data
  // ...
}

// In transform functions:
const armApprovalStatus = arm.approval_status;  // From backend
const finalStatus = getApprovalStatus(treatmentName, armApprovalStatus);
```

### 3. Display Components

```tsx
// Components just display what backend provides
<Badge className={treatment.approvalStatus === 'Approved' ? 'approved' : 'investigational'}>
  {treatment.approvalStatus === 'Approved' && '★ '}
  {treatment.approvalStatus}
</Badge>
```

## Why This Is Clean

### ✅ Separation of Concerns
- **Backend**: Owns classification logic and data
- **Frontend**: Only displays status

### ✅ Single Source of Truth
- All approval rules in `approval_status.txt`
- Auto-generated configs ensure consistency
- No duplicated logic between backend/frontend

### ✅ Backward Compatible
- Frontend falls back to simple matching for old data
- New data automatically uses backend status
- Gradual migration path

### ✅ Indication-Specific
```
Ipilimumab + Nivolumab:
├─ Resected Cutaneous Melanoma → "Investigational" ❌
└─ Unresectable Cutaneous Melanoma → "Approved" ✅
```

### ✅ Type-Safe
- Backend: Python type hints + Pydantic models
- Frontend: TypeScript interfaces
- Validated at both ends

## Updating Approval Status

### When Approval Rules Change

```bash
cd melanoma

# 1. Update source data
# Edit: data/deployed/approval_status.txt

# 2. Regenerate configs
python3 scripts/generate_approval_yaml.py

# 3. Run tests
python3 tests/test_therapy_classifier.py
python3 tests/test_approval_status_service.py

# 4. Restart backend (auto-loads new JSON)
# Frontend automatically uses new data
```

### Adding New Approved Therapy

Edit `approval_status.txt`:
```
Nivolumab + Relatlimab	Unresectable Cutaneous Melanoma	Approved
```

Regenerate → Backend automatically classifies correctly → Frontend displays ★

## Testing

### Backend Tests
```bash
cd melanoma
python3 tests/test_therapy_classifier.py  # Core classifier
python3 tests/test_approval_status_service.py  # Service integration
```

### Integration Test
```python
from src.app.json_trials_service import JSONTrialsService

service = JSONTrialsService(enable_approval_status=True)
abstract = service.get_full_abstract_by_id("ASCO_2020_10000")

# Verify approval_status present in all arms
for arm_key, arm_data in abstract["arm_results"].items():
    assert "approval_status" in arm_data
    print(f"{arm_data['arm_name']}: {arm_data['approval_status']}")
```

## Benefits

1. **Accurate**: Uses 995 arm+indication combinations, not ~15 drug names
2. **Maintainable**: Update one file → everything updates
3. **Auditable**: YAML file is human-readable
4. **Testable**: Comprehensive test suite
5. **Scalable**: Can handle thousands of therapies
6. **Context-aware**: Same drug, different status by indication

## Migration Status

✅ **Backend**: Fully implemented with enrichment  
✅ **Frontend**: Updated to use backend status when available  
✅ **Tests**: All passing (6 test suites)  
✅ **Configs**: Auto-generated from source data  
✅ **Documentation**: Complete  

**Status**: Ready for production use! 🚀
