"""Marker PDF processor implementation using the marker-pdf library."""

import gc
import logging
import re
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any, Optional

try:
    from marker.config.parser import ConfigParser  # type: ignore
    from marker.converters.pdf import PdfConverter  # type: ignore
    from marker.models import create_model_dict  # type: ignore
    from marker.output import text_from_rendered  # type: ignore
except ImportError as e:
    raise ImportError(
        "marker-pdf dependencies are required for MarkerPDFProcessor. "
        "Install with: poetry install --with processing"
    ) from e

from ..domain.interfaces import PDFProcessorInterface

logger = logging.getLogger(__name__)


class ModelManager:
    """Singleton manager for Marker models to avoid repeated loading."""

    _instance: Optional["ModelManager"] = None
    _model_dict: Optional[dict] = None

    def __new__(cls) -> "ModelManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_model_dict(self) -> dict:
        """Get or create the model dictionary."""
        if self._model_dict is None:
            logger.info("🧠 Loading Marker models (one-time initialization)...")
            try:
                self._model_dict = create_model_dict()
                logger.info("✅ Marker models loaded successfully")
            except Exception as e:
                logger.error(f"❌ Failed to load Marker models: {e}")
                raise
        return self._model_dict

    def cleanup(self) -> None:
        """Clean up models and free memory."""
        if self._model_dict is not None:
            del self._model_dict
            self._model_dict = None
            gc.collect()
            logger.info("✅ Model cleanup completed")


class MarkerPDFProcessor(PDFProcessorInterface):
    """Marker-based PDF processor implementation with superior accuracy and efficiency."""

    def __init__(self, use_llm: bool = False, extract_images: bool = True) -> None:
        """Initialize the Marker PDF processor.

        Args:
            use_llm: Whether to use LLM for improved accuracy (slower but better)
            extract_images: Whether to extract images from PDFs
        """
        self.use_llm = use_llm
        self.extract_images = extract_images
        self._model_manager = ModelManager()

        # Balanced configuration optimized for speed and accuracy
        self.config = {
            "output_format": "markdown",
            "extract_images": extract_images,
            "paginate_output": True,
            "keep_pageheader_in_output": True,
            "format_lines": False,
            "use_llm": use_llm,
            "redo_inline_math": False,
            "debug": False,
            "workers": 1,
        }

        # Processing statistics
        self.stats: dict[str, Any] = {
            "successful": 0,
            "failed": 0,
            "total_time": 0,
            "start_time": None,
            "failed_files": [],
        }

    async def validate_pdf(self, file_content: bytes) -> bool:
        """Validate that the file is a valid PDF using Marker."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(file_content)
                temp_file.flush()

                try:
                    # Use cached models for efficiency
                    config_parser = ConfigParser(self.config)
                    converter = PdfConverter(
                        config=config_parser.generate_config_dict(),
                        artifact_dict=self._model_manager.get_model_dict(),
                        processor_list=config_parser.get_processors(),
                        renderer=config_parser.get_renderer(),
                    )

                    # Try to build document structure
                    doc = converter.build_document(str(temp_path))
                    if doc and hasattr(doc, "pages") and len(doc.pages) > 0:
                        logger.info(
                            f"✅ PDF validation successful: {len(doc.pages)} pages"
                        )
                        return True
                    else:
                        logger.warning("⚠️ PDF validation failed: no pages found")
                        return False

                except Exception as e:
                    logger.error(f"❌ PDF validation error: {str(e)}")
                    return False
                finally:
                    # Clean up temp file
                    if temp_path.exists():
                        temp_path.unlink()

        except Exception as e:
            logger.error(f"❌ PDF validation failed: {str(e)}")
            return False

    async def is_batch_pdf(self, file_content: bytes) -> bool:
        """Determine if a PDF contains multiple documents using Marker."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(file_content)
                temp_file.flush()

                try:
                    # Use cached models for efficiency
                    config_parser = ConfigParser(self.config)
                    converter = PdfConverter(
                        config=config_parser.generate_config_dict(),
                        artifact_dict=self._model_manager.get_model_dict(),
                        processor_list=config_parser.get_processors(),
                        renderer=config_parser.get_renderer(),
                    )

                    # Build document to analyze structure
                    doc = converter.build_document(str(temp_path))
                    if not doc or not hasattr(doc, "pages"):
                        return False

                    # Check if PDF has multiple pages
                    if len(doc.pages) <= 1:
                        return False

                    # Batch detection indicators for scientific documents
                    batch_indicators = [
                        "Abstract ID",
                        "Abstract ID:",
                        "Abstract:",
                        "ABSTRACT:",
                        "Publication ID",
                        "Publication ID:",
                        "Title:",
                        "TITLE:",
                        "Authors:",
                        "AUTHORS:",
                        "Introduction",
                        "INTRODUCTION",
                        "Methods",
                        "METHODS",
                        "Results",
                        "RESULTS",
                        "Conclusion",
                        "CONCLUSION",
                    ]

                    for page_num in range(min(3, len(doc.pages))):
                        page = doc.pages[page_num]
                        if hasattr(page, "blocks") and page.blocks:
                            for block in page.blocks:
                                if hasattr(block, "text") and block.text:
                                    for indicator in batch_indicators:
                                        if indicator in block.text:
                                            logger.info(
                                                f"📋 Found batch indicator: {indicator}"
                                            )
                                            return True

                    # Check if pages have very different content
                    if len(doc.pages) > 2:
                        page1_text = self._extract_page_text(doc.pages[0])[:200]
                        page2_text = self._extract_page_text(doc.pages[1])[:200]

                        if self._is_different_content(page1_text, page2_text):
                            logger.info("📄 Different content detected between pages")
                            return True

                    return False

                except Exception as e:
                    logger.error(f"❌ Error analyzing PDF structure: {str(e)}")
                    return False
                finally:
                    # Clean up temp file
                    if temp_path.exists():
                        temp_path.unlink()

        except Exception as e:
            logger.error(f"❌ Error checking if PDF is batch: {str(e)}")
            return False

    async def extract_text(self, file_content: bytes) -> str:
        """Extract text content from PDF using Marker with improved efficiency."""
        start_time = time.time()

        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(file_content)
                temp_file.flush()

                try:
                    # Use cached models for efficiency
                    config_parser = ConfigParser(self.config)
                    converter = PdfConverter(
                        config=config_parser.generate_config_dict(),
                        artifact_dict=self._model_manager.get_model_dict(),
                        processor_list=config_parser.get_processors(),
                        renderer=config_parser.get_renderer(),
                    )

                    # Process PDF to markdown
                    logger.info("🔄 Processing PDF with Marker...")
                    rendered = converter(str(temp_path))
                    main_text, _, _ = text_from_rendered(rendered)

                    if not main_text:
                        raise Exception("No text content extracted from PDF")

                    # Extract headers and combine with main text
                    header_info = self._extract_headers_from_rendered(rendered)

                    if header_info:
                        final_text = header_info + "\n\n" + main_text
                    else:
                        final_text = main_text

                    elapsed = time.time() - start_time
                    logger.info(
                        f"✅ Text extraction successful (length: {len(final_text)}, time: {elapsed:.2f}s)"
                    )

                    if isinstance(self.stats["successful"], int):
                        self.stats["successful"] += 1
                    return final_text

                except Exception as e:
                    if isinstance(self.stats["failed"], int):
                        self.stats["failed"] += 1
                    logger.error(f"❌ Text extraction error: {str(e)}")
                    logger.debug(traceback.format_exc())
                    raise
                finally:
                    # Clean up temp file
                    if temp_path.exists():
                        temp_path.unlink()
                    # Force garbage collection to free memory
                    gc.collect()

        except Exception as e:
            logger.error(f"❌ Text extraction failed: {str(e)}")
            raise

    async def extract_metadata(self, file_content: bytes) -> dict[str, Any]:
        """Extract metadata from PDF using Marker with enhanced error handling."""
        start_time = time.time()

        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(file_content)
                temp_file.flush()

                try:
                    # Configure for JSON output to access metadata
                    json_config = self.config.copy()
                    json_config["output_format"] = "json"

                    # Use cached models for efficiency
                    config_parser = ConfigParser(json_config)
                    converter = PdfConverter(
                        config=config_parser.generate_config_dict(),
                        artifact_dict=self._model_manager.get_model_dict(),
                        processor_list=config_parser.get_processors(),
                        renderer=config_parser.get_renderer(),
                    )

                    # Convert to JSON to access metadata
                    logger.info("🔄 Extracting metadata with Marker...")
                    rendered = converter(str(temp_path))

                    metadata = {}
                    if hasattr(rendered, "metadata") and rendered.metadata:
                        metadata.update(rendered.metadata)

                    # Add processing info
                    elapsed = time.time() - start_time
                    metadata.update(
                        {
                            "processor": "marker",
                            "processor_version": "enhanced",
                            "use_llm": self.use_llm,
                            "extract_images": self.extract_images,
                            "processing_timestamp": time.time(),
                            "processing_time_seconds": elapsed,
                            "file_size_bytes": len(file_content),
                        }
                    )

                    logger.info(
                        f"✅ Metadata extraction successful (time: {elapsed:.2f}s)"
                    )
                    return metadata

                except Exception as e:
                    logger.error(f"❌ Metadata extraction error: {str(e)}")
                    logger.debug(traceback.format_exc())

                    # Return minimal metadata on failure
                    return {
                        "processor": "marker",
                        "processor_version": "enhanced",
                        "use_llm": self.use_llm,
                        "extract_images": self.extract_images,
                        "processing_timestamp": time.time(),
                        "error": str(e),
                        "file_size_bytes": len(file_content),
                    }
                finally:
                    # Clean up temp file
                    if temp_path.exists():
                        temp_path.unlink()
                    # Force garbage collection
                    gc.collect()

        except Exception as e:
            logger.error(f"❌ Metadata extraction failed: {str(e)}")
            return {
                "processor": "marker",
                "error": str(e),
                "processing_timestamp": time.time(),
            }

    def _extract_page_text(self, page) -> str:
        """Extract text from a page object with improved handling."""
        text_parts = []

        if hasattr(page, "blocks") and page.blocks:
            for block in page.blocks:
                if hasattr(block, "text") and block.text:
                    text_parts.append(block.text.strip())
                elif hasattr(block, "html") and block.html:
                    # Clean HTML tags
                    clean_text = re.sub(r"<[^>]+>", "", block.html).strip()
                    if clean_text:
                        text_parts.append(clean_text)

        return " ".join(text_parts)

    def _is_different_content(self, text1: str, text2: str) -> bool:
        """Check if two text samples are significantly different."""
        if not text1 or not text2:
            return True

        # Simple similarity check - can be improved
        words1 = set(text1.lower().split()[:50])  # First 50 words
        words2 = set(text2.lower().split()[:50])

        if not words1 or not words2:
            return True

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        similarity = intersection / union if union > 0 else 0
        return similarity < 0.3  # Less than 30% similarity

    def _extract_headers_from_rendered(self, rendered) -> str:
        """Extract headers from the rendered output with improved detection."""
        header_info = ""

        if hasattr(rendered, "children") and rendered.children:
            for i, page_data in enumerate(rendered.children, 1):
                page_headers = []

                # Extract headers from PageHeader blocks
                if hasattr(page_data, "children") and page_data.children:
                    for block in page_data.children:
                        if (
                            hasattr(block, "block_type")
                            and block.block_type == "PageHeader"
                        ):
                            if hasattr(block, "html") and block.html:
                                clean_text = re.sub(r"<[^>]+>", "", block.html).strip()
                                if (
                                    clean_text
                                    and clean_text
                                    != "Text that appears at the top of a page, like a page title."
                                ):
                                    page_headers.append(clean_text)

                # Fallback: extract headers from page HTML patterns
                if not page_headers and hasattr(page_data, "html") and page_data.html:
                    header_patterns = re.findall(r"<p>([^<]+)</p>", page_data.html)
                    for pattern in header_patterns:
                        clean_pattern = pattern.strip()
                        if (
                            clean_pattern
                            and len(clean_pattern) > 5
                            and clean_pattern.isupper()
                        ):
                            page_headers.append(clean_pattern)

                if page_headers:
                    header_info += (
                        f"\n--- Page {i} Header ---\n"
                        + "\n".join(page_headers)
                        + "\n---\n\n"
                    )

        return header_info

    def get_processing_stats(self) -> dict[str, Any]:
        """Get current processing statistics with enhanced metrics."""
        stats = self.stats.copy()
        if stats["start_time"] and isinstance(stats["start_time"], (int, float)):
            stats["total_runtime"] = time.time() - stats["start_time"]
            successful = stats.get("successful", 0)
            failed = stats.get("failed", 0)
            if isinstance(successful, int) and isinstance(failed, int):
                total_processed = successful + failed
                if total_processed > 0:
                    stats["success_rate"] = successful / total_processed
                    if isinstance(stats["total_runtime"], (int, float)):
                        stats["avg_time_per_file"] = (
                            stats["total_runtime"] / total_processed
                        )
        return stats

    def reset_stats(self) -> None:
        """Reset processing statistics."""
        self.stats = {
            "successful": 0,
            "failed": 0,
            "total_time": 0,
            "start_time": None,
            "failed_files": [],
        }

    def cleanup(self) -> None:
        """Clean up resources and models."""
        try:
            self._model_manager.cleanup()
            gc.collect()
            logger.info("✅ MarkerPDFProcessor cleanup completed")
        except Exception as e:
            logger.warning(f"⚠️ Error during processor cleanup: {e}")

    def __enter__(self) -> "MarkerPDFProcessor":
        """Context manager entry."""
        self.stats["start_time"] = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit with cleanup."""
        if exc_type is not None:
            logger.error(f"❌ Error in processor context: {exc_val}")
        self.cleanup()
