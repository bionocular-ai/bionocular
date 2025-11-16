# 🔑 Keyword Variations Reference Guide

## Quick Reference for Time Unit Variations

### Supported Formats

Our keyword filtering now handles ALL these variations automatically:

#### 1. **Hyphenated Formats** (normalized to spaces)
- `3.05-yr` → matches `3.05 yr`
- `12-month` → matches `12 month`
- `1-year` → matches `1 year`
- `6-mo` → matches `6 mo`

#### 2. **Concatenated Formats** (no separator)
- `12mo` ✅ Direct match
- `1yr` ✅ Direct match
- `12m` ✅ Direct match
- `1y` ✅ Direct match
- `24m` ✅ Direct match
- `2yr` ✅ Direct match

#### 3. **Spelled Out Formats**
- `one-year` → matches `one year`
- `twelve-month` → matches `twelve month`
- `two years` ✅ Direct match
- `three years` ✅ Direct match

#### 4. **Space-Separated Formats**
- `12 months` ✅ Direct match
- `1 year` ✅ Direct match
- `6 mo` ✅ Direct match
- `24 mth` ✅ Direct match

#### 5. **Abbreviation Variations**
- `mo` = month
- `yr` = year
- `y` = year
- `mth` = month
- `mths` = months
- `m` = month (context-dependent)

#### 6. **Plural/Singular**
- Both `month` and `months` ✅
- Both `year` and `years` ✅

---

## Complete Time Unit Keywords by Timepoint

### 6 Months
```python
["6 month", "6 months", "6 mo", "6m", "6 mth", "6 mths", "six month", "six months"]
```

### 9 Months
```python
["9 month", "9 months", "9 mo", "9m", "9 mth", "9 mths", "nine month", "nine months"]
```

### 12 Months / 1 Year
```python
["12 month", "12 months", "12 mo", "12mo", "12m", 
 "1 year", "1 years", "1 yr", "1yr", "1 y", "1y", 
 "12 mth", "12 mths", "one year", "twelve month", "twelve months"]
```

### 18 Months
```python
["18 month", "18 months", "18 mo", "18mo", "18m", "18 mth", "18 mths"]
```

### 24 Months / 2 Years
```python
["24 month", "24 months", "24 mo", "24mo", "24m", 
 "2 year", "2 years", "2 yr", "2yr", "2 y", "2y", 
 "24 mth", "24 mths", "two year", "two years"]
```

### 36 Months / 3 Years
```python
["36 month", "36 months", "36 mo", "36mo", "36m", 
 "3 year", "3 years", "3 yr", "3yr", "3 y", "3y", 
 "36 mth", "36 mths", "three year", "three years"]
```

### 48 Months / 4 Years
```python
["48 month", "48 months", "48 mo", "48mo", "48m", 
 "4 year", "4 years", "4 yr", "4yr", "4 y", "4y", 
 "48 mth", "48 mths", "four year", "four years"]
```

---

## Grouped AND Logic Examples

### Example 1: HR_EFS (Hazard Ratio for Event-Free Survival)

**Requires BOTH keyword groups to match:**

```python
AttributeType.HR_EFS: [
    ["efs", "event-free", "event free"],  # Group 1: Must have EFS keyword
    ["hr", "hazard ratio"]                 # Group 2: Must have HR keyword
]
```

**Matches:**
- ✅ "HR for EFS was 0.75"
- ✅ "Event-free survival hazard ratio 0.75"
- ✅ "hazard ratio (HR) for event free survival"

**Rejects:**
- ❌ "HR for RFS was 0.75" (has HR but not EFS)
- ❌ "EFS rate was 58%" (has EFS but not HR)
- ❌ "PFS HR was 0.80" (has HR but not EFS)

### Example 2: PFS_RATE_12M

**Requires BOTH keyword groups to match:**

```python
AttributeType.PFS_RATE_12M: [
    ["pfs", "progression-free", "progression free"],  # Group 1: Must have PFS
    ["12 month", "12 months", "12mo", "12m", "1 year", "1yr", ...]  # Group 2: Must have 12M/1Y
]
```

**Matches:**
- ✅ "12-month PFS rate was 58%"
- ✅ "PFS at 1 year was 60%"
- ✅ "progression-free survival at 12mo"
- ✅ "1yr PFS rate"

**Rejects:**
- ❌ "12-month OS rate was 85%" (has timepoint but not PFS)
- ❌ "PFS at 6 months was 70%" (has PFS but wrong timepoint)
- ❌ "24-month PFS rate" (has PFS but wrong timepoint)

### Example 3: GRADE_3_PLUS_TEAE

**Requires BOTH keyword groups to match:**

```python
AttributeType.GRADE_3_PLUS_TEAE: [
    ["teae", "treatment emergent"],           # Group 1: Must have TEAE
    ["grade 3", "grade 4", "grade ≥3", "g3"]  # Group 2: Must have grade
]
```

**Matches:**
- ✅ "Grade 3+ TEAEs occurred in 45%"
- ✅ "Treatment-emergent grade 3 adverse events"
- ✅ "Grade ≥3 TEAE rate"

**Rejects:**
- ❌ "Grade 3+ TRAEs" (has grade but not TEAE)
- ❌ "Grade 3+ AEs" (has grade but not TEAE)
- ❌ "TEAEs occurred in 60%" (has TEAE but no grade)

---

## How Normalization Works

### Text Preprocessing
Before keyword matching, the chunk content is normalized:

```python
content_lower = chunk_content.lower()
content_normalized = content_lower.replace('-', ' ').replace('_', ' ')
```

**Examples:**
- `"3.05-yr median follow-up"` → `"3.05 yr median follow up"`
- `"12-month PFS"` → `"12 month pfs"`
- `"event-free survival"` → `"event free survival"`
- `"Grade_3_TEAE"` → `"grade 3 teae"`

### Word Boundary Matching
Keywords use regex word boundaries (`\b`) for exact matching:

```python
pattern = r'\b' + re.escape(keyword) + r'\b'
```

**Examples:**
- ✅ `"cr"` matches `"The CR rate was 25%"` 
- ❌ `"cr"` does NOT match `"The patient walked across the room"` 

---

## Adding New Keywords

### For Simple Attributes (OR logic)
Just add to the list:

```python
AttributeType.MEDIAN_PFS: [
    "pfs", 
    "progression-free survival", 
    "progression free survival",
    "progression free",  # <-- Add new variations here
]
```

### For Compound Attributes (AND logic)
Add to the appropriate group:

```python
AttributeType.HR_PFS: [
    ["pfs", "progression-free", "progression free", "prog free"],  # Add to Group 1
    ["hr", "hazard ratio", "hazard"]                               # Add to Group 2
]
```

---

## Testing Keywords

Use the test script to validate:

```bash
poetry run python test_grouped_keywords.py
```

Or run a focused test:

```python
from query_all_numeric_attributes import chunk_contains_keywords

# Test simple OR matching
keywords = ["pfs", "progression-free"]
result = chunk_contains_keywords("The PFS was 12 months", keywords)
print(result)  # True

# Test grouped AND matching
keywords = [
    ["pfs", "progression-free"],
    ["12 month", "1 year"]
]
result = chunk_contains_keywords("12-month PFS was 58%", keywords)
print(result)  # True

result = chunk_contains_keywords("6-month PFS was 70%", keywords)
print(result)  # False (wrong timepoint)
```

---

## 🎯 Best Practices

1. **Always include plural and singular forms** (`month` + `months`)
2. **Include hyphenated AND non-hyphenated** (`event-free` + `event free`)
3. **Add common abbreviations** (`pfs`, `os`, `mo`, `yr`)
4. **Use grouped AND for compound attributes** (prevents cross-contamination)
5. **Test with real abstract text** (use the comprehensive test script)
6. **Start broad, then narrow** (if too many false positives, add more specific keywords)

---

## 📊 Coverage Statistics

**Total Attributes with Keywords:** 73/76 (96.1%)
- **Grouped AND Logic:** 50 attributes
- **Simple OR Logic:** 23 attributes
- **No Keywords (API-sourced):** 3 attributes (MINIMUM_AGE, MAXIMUM_AGE, SEX)

**Time Unit Coverage:**
- All rate attributes: 6M, 9M, 12M/1Y, 18M, 24M/2Y, 36M/3Y, 48M/4Y ✅
- All follow-up attributes ✅
- Comprehensive abbreviation support ✅

---

**Last Updated:** November 4, 2025  
**Implementation:** `query_all_numeric_attributes.py` (ATTRIBUTE_KEYWORDS)  
**Function:** `chunk_contains_keywords()`  

