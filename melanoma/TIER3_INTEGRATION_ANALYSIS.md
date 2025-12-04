# 🔍 Senior Dev Analysis: Tier 3 Keyword Filtering Integration

## Executive Summary

**Status:** ❌ **Tier 3 keyword filtering is NOT implemented in production**

**Current State:**
- ✅ **Tier 1** (metadata filtering) is implemented in `arm_aware_rag_provider.py`
- ✅ **Tier 2** (sub-chunking) is implemented in `langchain/chunking.py`
- ❌ **Tier 3** (keyword filtering) exists only in test script `query_all_numeric_attributes.py`

**Impact:** Production extraction is retrieving **93.3% false positives** that could be filtered out.

---

## Detailed Analysis

### 1. Current Production Implementation

**File:** `src/infrastructure/arm_aware_rag_provider.py`

```python
# Line 157-163: ✅ TIER 1 IMPLEMENTED
if required_chunk_types:
    search_filters["chunk_type"] = required_chunk_types
    logger.debug(f"Filtering {attribute_type.value} to chunk types: {required_chunk_types}")

# Line 179-187: ⚠️ TIER 2 (NOT TIER 3)
if RAGOptimizationConfig.should_include_chunk(result.chunk.content, attribute_type):
    all_search_results.append(result)
```

**What `should_include_chunk` actually does:**
```python
# File: src/domain/rag_optimization_config.py (lines 198-223)
def should_include_chunk(chunk_content: str, attribute_type: AttributeType) -> bool:
    """Filters only NCT and Sponsor chunks - NOT keyword filtering"""
    chunk_type = RAGOptimizationConfig._classify_chunk(chunk_content)
    
    # NCT chunks only for NCT-dependent attributes
    if chunk_type == ChunkRelevanceType.NCT_INFO:
        return attribute_type in RAGOptimizationConfig.NCT_DEPENDENT_ATTRIBUTES
    
    # Sponsor chunks only for sponsor attributes
    if chunk_type == ChunkRelevanceType.SPONSOR_INFO:
        return attribute_type in RAGOptimizationConfig.SPONSOR_DEPENDENT_ATTRIBUTES
    
    # All other chunks pass through WITHOUT keyword validation
    return True
```

**Result:** This only filters NCT/Sponsor info, **not** semantic false positives like:
- ❌ HR chunks matching EFS queries
- ❌ RFS chunks matching PFS queries  
- ❌ Wrong timepoint chunks (6M matching 12M queries)

---

### 2. Test Script Implementation (Tier 3)

**File:** `query_all_numeric_attributes.py`

```python
# Lines 300-345: ✅ TIER 3 IMPLEMENTED
def chunk_contains_keywords(chunk_content: str, keywords) -> bool:
    """Check if chunk contains required keywords (whole word matching).
    
    Handles:
    - List[str] for OR matching
    - List[List[str]] for grouped AND matching
    - Whole-word boundaries to prevent partial matches
    - Hyphen/underscore normalization
    """
    content_normalized = chunk_content.lower().replace('-', ' ').replace('_', ' ')
    
    # Grouped AND matching
    if keywords and isinstance(keywords[0], list):
        for group in keywords:
            group_matched = False
            for keyword in group:
                pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
                if re.search(pattern, content_normalized):
                    group_matched = True
                    break
            if not group_matched:
                return False
        return True
    
    # Simple OR matching
    else:
        for keyword in keywords:
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            if re.search(pattern, content_normalized):
                return True
        return False

# Lines 348-366: Filter application
def filter_results_by_keywords(results, keywords):
    filtered = []
    rejected = []
    for result in results:
        if chunk_contains_keywords(result.chunk.content, keywords):
            filtered.append(result)
        else:
            rejected.append(result)
    return filtered, rejected
```

**Comprehensive keyword mappings (lines 46-238):**
- 50 attributes with grouped AND logic
- 23 attributes with simple OR matching
- All time unit variations (12mo, 1yr, 12-month, etc.)
- Whole-word matching prevents partial matches

---

## Gap Analysis

### Missing in Production

| Feature | Test Script | Production | Impact |
|---------|-------------|------------|--------|
| **Grouped AND Logic** | ✅ 50 attributes | ❌ None | HR_EFS matches RFS chunks |
| **Time Unit Variations** | ✅ All formats | ❌ None | "12mo" not recognized |
| **Whole-word Matching** | ✅ Regex `\b` | ❌ None | "cr" matches "across" |
| **Keyword Mappings** | ✅ 73 attributes | ❌ None | No filtering |
| **False Positive Rejection** | ✅ 93.3% | ❌ 0% | Wasted LLM tokens |

---

## Implementation Strategy

### Option 1: Direct Integration (Recommended) ⭐

**Pros:**
- Reuses battle-tested logic from test script
- Minimal code duplication
- Consistent behavior

**Cons:**
- Requires moving keyword mappings to shared location

**Implementation Steps:**

1. **Move keyword mappings to config** (create new file)
   ```python
   # src/domain/attribute_keywords.py
   from typing import Dict, List, Union
   from .extraction_models import AttributeType
   
   # Keyword mappings for Tier 3 filtering
   ATTRIBUTE_KEYWORDS: Dict[AttributeType, Union[List[str], List[List[str]]]] = {
       # Copy from query_all_numeric_attributes.py lines 46-238
       AttributeType.MEDIAN_PFS: ["pfs", "progression-free survival", ...],
       AttributeType.HR_EFS: [
           ["efs", "event-free"],
           ["hr", "hazard ratio"]
       ],
       # ... etc
   }
   ```

2. **Move filtering logic to shared module**
   ```python
   # src/infrastructure/keyword_filter.py
   import re
   from typing import List, Union
   
   def chunk_contains_keywords(
       chunk_content: str,
       keywords: Union[List[str], List[List[str]]]
   ) -> bool:
       """Check if chunk contains required keywords (whole word matching)."""
       # Copy implementation from query_all_numeric_attributes.py
       # lines 300-345
       ...
   ```

3. **Update `RAGOptimizationConfig.should_include_chunk`**
   ```python
   # src/domain/rag_optimization_config.py
   from .attribute_keywords import ATTRIBUTE_KEYWORDS
   from ..infrastructure.keyword_filter import chunk_contains_keywords
   
   @staticmethod
   def should_include_chunk(
       chunk_content: str,
       attribute_type: AttributeType
   ) -> bool:
       """Enhanced filtering with Tier 3 keyword validation."""
       
       # TIER 2: NCT/Sponsor filtering (existing)
       chunk_type = RAGOptimizationConfig._classify_chunk(chunk_content)
       
       if chunk_type == ChunkRelevanceType.NCT_INFO:
           return attribute_type in RAGOptimizationConfig.NCT_DEPENDENT_ATTRIBUTES
       
       if chunk_type == ChunkRelevanceType.SPONSOR_INFO:
           return attribute_type in RAGOptimizationConfig.SPONSOR_DEPENDENT_ATTRIBUTES
       
       # 🎯 TIER 3: Keyword filtering (NEW)
       keywords = ATTRIBUTE_KEYWORDS.get(attribute_type)
       if keywords:
           return chunk_contains_keywords(chunk_content, keywords)
       
       # No keywords defined = include chunk
       return True
   ```

4. **No changes needed to `arm_aware_rag_provider.py`**
   - Tier 3 automatically activated via `should_include_chunk`
   - Existing call on line 179 now includes keyword filtering

---

### Option 2: Separate Filtering Step

**Pros:**
- More explicit
- Easier to disable/enable

**Cons:**
- More code changes
- Potential performance impact (extra loop)

**Implementation:**
```python
# In arm_aware_rag_provider.py, after line 195

# 🎯 TIER 3: Apply keyword filtering
from ..infrastructure.keyword_filter import apply_keyword_filter

if attribute_type in ATTRIBUTE_KEYWORDS:
    all_search_results = apply_keyword_filter(
        all_search_results,
        attribute_type
    )
```

---

## Recommended Approach

**Go with Option 1** for these reasons:

1. **Minimal Changes:** Only modifies `should_include_chunk`, leveraging existing call
2. **Consistent:** Same filtering logic everywhere
3. **Maintainable:** Keywords centralized in one place
4. **Testable:** Easy to unit test keyword logic
5. **Performance:** No extra loops, filtering happens during deduplication

---

## Implementation Checklist

- [ ] Create `src/domain/attribute_keywords.py` with all keyword mappings
- [ ] Create `src/infrastructure/keyword_filter.py` with filtering logic
- [ ] Update `src/domain/rag_optimization_config.py` to use Tier 3 filtering
- [ ] Add unit tests for keyword filtering
- [ ] Update `demo_enhanced_extraction.py` to use Tier 3
- [ ] Run comprehensive test to verify integration
- [ ] Update documentation

---

## Expected Impact

### Before Tier 3 Integration
```
Query: HR_EFS
Retrieved: 30 chunks
- 27 false positives (has "HR" but wrong metric: RFS, PFS, MFS)
- 3 true positives (has both "HR" and "EFS")
LLM processes: 30 chunks (90% wasted tokens)
```

### After Tier 3 Integration
```
Query: HR_EFS  
Retrieved: 30 chunks
Keyword Filter: 27 rejected, 3 passed
LLM processes: 3 chunks (90% token savings)
```

**Cost Savings:**
- Reduce RAG context by ~90%
- Lower LLM costs proportionally
- Faster extraction (fewer tokens to process)
- Higher precision (less noise for LLM)

---

## Testing Strategy

1. **Unit Tests** - Test keyword matching logic
   ```python
   def test_grouped_and_matching():
       keywords = [["pfs"], ["hr"]]
       assert chunk_contains_keywords("PFS HR was 0.75", keywords) == True
       assert chunk_contains_keywords("RFS HR was 0.75", keywords) == False
   ```

2. **Integration Tests** - Test with real abstracts
   ```python
   async def test_tier3_in_extraction():
       result = await extraction_service.extract_attribute(
           AttributeType.HR_EFS, abstract_id="10000"
       )
       # Verify no RFS chunks in context
       for chunk in result.source_chunks:
           assert "rfs" not in chunk.content.lower() or "efs" in chunk.content.lower()
   ```

3. **Regression Tests** - Compare before/after
   ```bash
   # Run demo with and without Tier 3
   poetry run python demo_enhanced_extraction.py
   # Compare token usage, precision, and extraction accuracy
   ```

---

## Risk Analysis

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Over-filtering** | Medium | High | Start with permissive keywords, tune based on false negatives |
| **Performance degradation** | Low | Medium | Regex is fast; filter after vector search, not before |
| **Keyword maintenance** | High | Low | Centralize in one file; add validation tests |
| **Breaking changes** | Low | High | Extensive testing; feature flag for gradual rollout |

---

## Rollout Plan

### Phase 1: Soft Launch (1 week)
- Implement in test environment only
- Run comprehensive tests
- Compare results with Tier 1+2 only
- Tune keyword mappings based on false positives/negatives

### Phase 2: Staged Rollout (2 weeks)
- Deploy to production with feature flag
- Enable for 10% of extractions
- Monitor precision, recall, and cost
- Adjust keywords as needed

### Phase 3: Full Deployment (1 week)
- Enable for 100% of extractions
- Remove feature flag
- Update all documentation
- Train team on keyword management

---

## Maintenance Considerations

### Adding New Attributes
```python
# Add to src/domain/attribute_keywords.py
AttributeType.NEW_METRIC: [
    ["metric_keyword"],
    ["qualifier_keyword"]  # If compound attribute
]
```

### Tuning Existing Keywords
- Monitor false negatives (attribute not extracted)
- Check extraction logs for keyword mismatches
- Add missing variations (e.g., new time unit formats)
- Remove overly broad keywords if false positives occur

### Performance Monitoring
- Track keyword filter rejection rate (target: 90-95%)
- Monitor extraction accuracy (should improve or stay same)
- Watch token usage (should decrease by 80-90%)
- Alert if rejection rate drops below 80% (indicates drift)

---

## Conclusion

**Tier 3 keyword filtering is battle-tested and ready for production.**

The test script demonstrates **93.3% false positive rejection** with:
- ✅ Grouped AND logic for compound attributes
- ✅ Comprehensive time unit variations
- ✅ Whole-word matching
- ✅ 73 attributes covered

**Recommendation:** Integrate immediately using Option 1 approach.

**Timeline:** 1-2 days for implementation, 1 week for testing and tuning.

**ROI:** ~90% reduction in LLM tokens → significant cost savings + faster extraction.

---

**Author:** Senior Dev Analysis  
**Date:** November 4, 2025  
**Status:** Ready for Implementation  

