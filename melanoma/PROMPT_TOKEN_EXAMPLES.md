# Actual Prompt Token Examples

## Example 1: MEDIAN_PFS (Simple Numeric Attribute)

### 1. BASE PROMPT (91 tokens)
```
📌 NOTE: The provided context has been pre-filtered using 3-tier optimization:
- Tier 1: Restricted to Results/Table/Conclusions sections
- Tier 2: Sub-chunked for precision
- Tier 3: Keyword-filtered to match the requested attribute

Extract the value directly from the relevant context.

Extract median PFS in months. Return numeric value or 'NR' if not reached.
```

### 2. CONTEXT CHUNKS (405 raw tokens, 414 formatted tokens)
**3 chunks** formatted as:
```
[Context 1]
### Results

**Efficacy**: The median progression-free survival (PFS) was 12.3 months (95% CI: 10.5-14.1) in the pembrolizumab arm compared to 8.2 months (95% CI: 7.1-9.3) in the placebo arm. The hazard ratio (HR) for PFS was 0.65 (95% CI: 0.52-0.81, p<0.001). Overall survival (OS) data showed similar trends with a median OS of 28.5 months versus 22.1 months (HR 0.72, 95% CI: 0.58-0.89, p=0.002). Objective response rate (ORR) was 45% (95% CI: 40-50%) in the pembrolizumab arm versus 20% (95% CI: 15-25%) in the placebo arm. Complete response (CR) rate was 12% versus 3%. Duration of response (DOR) was 18.5 months versus 10.2 months. Time to response (TTR) was 2.1 months versus 3.5 months.

[Context 2]
**Safety**: Grade 3 or higher treatment-related adverse events (TRAE) occurred in 15% of patients in the pembrolizumab arm versus 8% in the placebo arm. The most common adverse events included fatigue (35% vs 28%), rash (25% vs 12%), and diarrhea (20% vs 15%). Grade 3+ TRAE leading to treatment discontinuation occurred in 5% versus 2%. Serious TRAE occurred in 12% versus 6%. Immune-related adverse events (irAE) occurred in 18% versus 3%. TRAE leading to death occurred in 1% versus 0%.

[Context 3]
**Patient Characteristics**: A total of 514 patients were enrolled in the pembrolizumab arm and 257 patients in the placebo arm. Median age was 65 years (range: 18-85) in the pembrolizumab arm and 64 years (range: 19-84) in the placebo arm. Male patients comprised 58% versus 55%. ECOG performance status 0 was 62% versus 60%. BRAF mutation status was positive in 45% versus 43%. Prior systemic therapy was received by 35% versus 38%.
```

### 3. WRAPPER (249 tokens)
```
TASK: Extract the Median Pfs for ALL treatment arms in this clinical trial.

TREATMENT ARMS:
Arm 1 (arm_1): Pembrolizumab - Generic: pembrolizumab - Dose: 200 mg
Arm 2 (arm_2): Placebo - Generic: placebo

CRITICAL REQUIREMENTS:
1. Extract Median Pfs for EACH treatment arm separately - values MUST be arm-specific
2. Look for values that explicitly mention the arm name (e.g., "pembrolizumab (N=514)")
3. DO NOT use the same value for all arms unless explicitly stated as identical
4. If Median Pfs is not found for a specific arm, use "Not found"
5. Return values in the exact JSON format specified below
6. Be precise and accurate - this is for clinical data analysis

⚠️ ARM-SPECIFIC EXTRACTION:
- Each arm should have its own specific value
- Look for arm names in the context: Pembrolizumab, Placebo
- Values should differ between arms unless the study reports identical results

OUTPUT FORMAT (JSON):
{
  "arm_1": "value_for_arm_1",
  "arm_2": "value_for_arm_2",
  "arm_3": "value_for_arm_3"
}
```

**Total: 745 tokens** (249 wrapper + 91 base + 405 context)

---

## Example 2: NUMBER_OF_PATIENTS (Complex Attribute with Verification)

### 1. BASE PROMPT (165 tokens)
```
⚠️ ARM-SPECIFIC VERIFICATION:
✓ Extract ONLY arm-specific value (e.g., "pembrolizumab N=514")
✗ NOT study totals (e.g., "1019 randomized")
✗ NOT other arm values
Pattern: Value MUST be near arm name ("arm_name N=###", "arm: N=###")

📌 NOTE: The provided context has been pre-filtered using 3-tier optimization:
- Tier 1: Restricted to Results/Table/Conclusions sections
- Tier 2: Sub-chunked for precision
- Tier 3: Keyword-filtered to match the requested attribute

Extract the value directly from the relevant context.

Extract the number of patients in this specific treatment arm. Look for 'N=' or 'n=' immediately after the arm name. Return integer only.
```

### 2. CONTEXT CHUNKS (405 raw tokens, 414 formatted tokens)
Same as Example 1.

### 3. WRAPPER (255 tokens)
Same structure as Example 1, but with "Number Of Patients" instead of "Median Pfs".

**Total: 825 tokens** (255 wrapper + 165 base + 405 context)

---

## Example 3: TRIAL_NAME (Simple Attribute)

### 1. BASE PROMPT (27 tokens)
```
Extract trial name. Look for 'Keynote-', 'Checkmate-', 'Masterkey-' patterns. Return full name or 'No Name'.
```

### 2. CONTEXT CHUNKS (405 raw tokens, 414 formatted tokens)
Same as Example 1.

### 3. WRAPPER (249 tokens)
Same structure as Example 1, but with "Trial Name" instead of "Median Pfs".

**Total: 681 tokens** (249 wrapper + 27 base + 405 context)

---

## Key Observations

1. **Wrapper is consistent** (~249-255 tokens) across all attributes - this is the repetitive overhead
2. **Base prompt varies** (27-165 tokens) depending on attribute complexity
3. **Context is the largest component** (~405 tokens) - 3 chunks × ~135 tokens each
4. **Total prompt size**: ~680-850 tokens per call

## Optimization Opportunities

### 1. Wrapper Simplification (Save ~150 tokens)
**Current wrapper** (~249 tokens) is verbose with:
- Long task description
- 6 bullet points of requirements
- Arm-specific extraction warnings
- JSON format example

**Could be reduced to** (~100 tokens):
```
Extract {attr_name} for each arm. Return JSON: {{"arm_1": "value", "arm_2": "value"}}.

Arms: {arms_text}

{base_prompt}
```

### 2. Context Reduction (Save ~135 tokens)
**Current**: 3 chunks × ~135 tokens = ~405 tokens
**Proposed**: 2 chunks × ~135 tokens = ~270 tokens

### 3. Base Prompt Optimization (Save ~30 tokens)
Some base prompts are verbose (e.g., `number_of_patients` with arm-specific verification). Could be shortened.

## Total Potential Savings

- **Wrapper**: ~150 tokens saved
- **Context**: ~135 tokens saved  
- **Base prompts**: ~30 tokens saved
- **Total**: ~315 tokens per call (42% reduction)

**For 74 calls**: 23,310 tokens saved = **$0.058** cost reduction (53% of current prompt token cost)


