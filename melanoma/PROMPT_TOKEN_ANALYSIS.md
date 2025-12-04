# Prompt Token Analysis

## Summary

**Total Prompt Tokens: 32,100** across 74 LLM calls = **~434 tokens per call on average**

## Breakdown

### 1. Wrapper Tokens (~272 tokens per call)
The wrapper includes:
- Task description
- Treatment arms information
- Critical requirements (6 bullet points)
- Arm-specific extraction warnings
- JSON output format
- Final instruction

**Issue**: This ~272 token wrapper is repeated for EVERY attribute extraction call.

### 2. Base Prompt Tokens (~116 tokens per attribute)
Attribute-specific instructions from `prompt_templates.py`. Range: 31-173 tokens.

**Top offenders** (highest base prompt tokens):
- `number_of_patients`: 173 tokens
- `biomarkers_inclusion_criteria`: 155 tokens
- `biomarkers_exclusion_criteria`: 155 tokens
- `study_completion_date`: 151 tokens
- `clinical_trial_phase`: 151 tokens

### 3. Context Tokens (~300 tokens per call)
With 3 context chunks at ~100 tokens each = ~300 tokens of context per call.

## Cost Impact

- **Current**: 32,100 prompt tokens × $2.50/1M = **$0.08025** (78% of total cost)
- **Completion tokens**: 2,956 × $10.00/1M = **$0.02956** (22% of total cost)

## Recommendations

### 1. Simplify Wrapper (Save ~150 tokens per call)
**Current wrapper is verbose**. Can be reduced from ~272 to ~120 tokens:

**Before** (~272 tokens):
```
TASK: Extract the {attr_name} for ALL treatment arms in this clinical trial.

TREATMENT ARMS:
Arm 1 (arm_1): Pembrolizumab - Generic: pembrolizumab - Dose: 200 mg
Arm 2 (arm_2): Placebo

CRITICAL REQUIREMENTS:
1. Extract {attr_name} for EACH treatment arm separately - values MUST be arm-specific
2. Look for values that explicitly mention the arm name (e.g., "pembrolizumab (N=514)")
3. DO NOT use the same value for all arms unless explicitly stated as identical
4. If {attr_name} is not found for a specific arm, use "Not found"
5. Return values in the exact JSON format specified below
6. Be precise and accurate - this is for clinical data analysis

⚠️ ARM-SPECIFIC EXTRACTION:
- Each arm should have its own specific value
- Look for arm names in the context: Pembrolizumab, Placebo
- Values should differ between arms unless the study reports identical results

{base_prompt}

OUTPUT FORMAT (JSON):
{
  "arm_1": "value_for_arm_1",
  "arm_2": "value_for_arm_2",
  "arm_3": "value_for_arm_3"
}

IMPORTANT: Return ONLY the JSON object, no additional text or explanation.
```

**After** (~120 tokens):
```
Extract {attr_name} for each arm. Return JSON: {{"arm_1": "value", "arm_2": "value"}}.

Arms: {arms_text}

{base_prompt}
```

**Savings**: ~150 tokens × 74 calls = **~11,100 tokens** = **$0.02775** (27% reduction)

### 2. Reduce Context Chunks (Save ~100 tokens per call)
**Current**: 3 chunks × ~100 tokens = ~300 tokens
**Proposed**: 2 chunks × ~100 tokens = ~200 tokens

**Savings**: ~100 tokens × 74 calls = **~7,400 tokens** = **$0.0185** (23% reduction)

### 3. Optimize Base Prompts (Save ~30 tokens per call)
Review verbose base prompts (especially `number_of_patients`, biomarker criteria) and shorten them.

**Savings**: ~30 tokens × 74 calls = **~2,220 tokens** = **$0.00555** (7% reduction)

## Total Potential Savings

| Optimization | Tokens Saved | Cost Saved | % Reduction |
|-------------|--------------|------------|-------------|
| Simplify Wrapper | 11,100 | $0.02775 | 27% |
| Reduce Context | 7,400 | $0.0185 | 23% |
| Optimize Base Prompts | 2,220 | $0.00555 | 7% |
| **TOTAL** | **20,720** | **$0.0518** | **47%** |

**New total cost**: $0.10981 - $0.0518 = **$0.05801** (47% reduction)

## Implementation Priority

1. **High Priority**: Simplify wrapper (biggest impact, easiest to implement)
2. **Medium Priority**: Reduce context chunks from 3 to 2
3. **Low Priority**: Optimize verbose base prompts


