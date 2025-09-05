# Marker PDF Processor Configuration

## 🎯 **Working Configuration (Preserved from Original Script)**

The Marker processor is configured with settings that have been tested and optimized for melanoma research documents.

### **Core Settings**
```python
config = {
    "output_format": "markdown",         # Markdown output for proper formatting
    "extract_images": True,              # ENABLED - Extract images from PDFs
    "paginate_output": True,             # Keep page structure
    "keep_pageheader_in_output": True,   # Preserve page headers
    "format_lines": False,               # DISABLED - Better speed, good results
    "use_llm": False,                    # DISABLED - Better speed, good results
    "redo_inline_math": False,           # DISABLED - Better speed, good results
    "debug": False,                      # DISABLED - Production mode
    "workers": 1,                        # Single worker for stability
}
```

### **Why These Settings Work Well**

1. **`use_llm: False`** - LLM processing is slower and doesn't improve results significantly for our use case
2. **`format_lines: False`** - Line formatting can introduce artifacts, disabled for cleaner output
3. **`redo_inline_math: False`** - Math processing is slow and not needed for abstracts/publications
4. **`extract_images: True`** - Images are valuable for medical documents
5. **`keep_pageheader_in_output: True`** - Page headers contain important session information

### **Environment Variables**

```bash
# Marker-specific Settings
MARKER_USE_LLM=false                    # Default: false (for speed)
MARKER_EXTRACT_IMAGES=true              # Default: true (for medical docs)
```

### **Performance Characteristics**

- **Accuracy**: 95.67% (benchmarked vs LLaMAParse 84.24%)
- **Speed**: 0.18s/page (vs LLaMAParse 23.35s/page)
- **Memory**: ~3.17GB VRAM usage
- **Throughput**: 122 pages/second on H100

### **Best For**

- Scientific papers and abstracts
- Complex medical document layouts
- Documents with tables and structured content
- High accuracy requirements
- Batch processing of conference materials

### **Not Recommended For**

- Simple text-only documents (use PyPDF2 instead)
- Real-time processing requirements
- Low-memory environments
- Documents requiring LLM enhancement
