"""Load the source markdown an abstract or publication was extracted from.

The validation judge must grade against the same text the extractor read, so the
document split here mirrors the extraction pipelines exactly:

* publications - one ``.md`` per document, ``pub_id`` is the file stem
  (``run_publication_pipeline.py``).
* abstracts - one ``.md`` per conference-year holding many abstracts, split on
  ``### Abstract ID:`` and keyed ``{CONFERENCE}_{YEAR}_{ID}``
  (``run_abstract_pipeline.py``).

Each loaded document carries the SHA-256 of the exact text handed to the judge.
The extraction runs recorded no such hash, so this establishes provenance from now
on rather than verifying that the corpus has not drifted since extraction.
"""

from __future__ import annotations

import hashlib
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from ..domain.constants import AbstractPatterns, FileExtensions

logger = logging.getLogger(__name__)

# The extractor splits on the header without its trailing space, then prepends the
# same token back onto every block.
_ABSTRACT_SPLIT_TOKEN = AbstractPatterns.ABSTRACT_ID_HEADER.rstrip()
# Conference-year filenames, e.g. "ASCO_2023.md".
_YEAR_FILE_RE = re.compile(r"^(?P<conference>[A-Za-z]+)_(?P<year>\d{4})$")


class SourceDocumentNotFoundError(LookupError):
    """Raised when an extracted record's source document cannot be located."""


@dataclass(frozen=True)
class SourceDocument:
    """The source text for one extracted document, with its provenance hash."""

    doc_id: str
    text: str
    sha256: str
    path: Path


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class DocumentSourceLoader(ABC):
    """Resolves a ``doc_id`` from an extraction run to its source text."""

    @abstractmethod
    def load(self, doc_id: str) -> SourceDocument:
        """Return the source document, or raise ``SourceDocumentNotFoundError``."""
        raise NotImplementedError

    @abstractmethod
    def available_ids(self) -> set[str]:
        """Every ``doc_id`` this loader can resolve - used by ``--dry-run``."""
        raise NotImplementedError


class PublicationSourceLoader(DocumentSourceLoader):
    """One markdown file per publication, named after its ``pub_id``."""

    def __init__(self, publications_dir: Path) -> None:
        self._dir = publications_dir

    def load(self, doc_id: str) -> SourceDocument:
        path = self._dir / f"{doc_id}{FileExtensions.MARKDOWN}"
        if not path.exists():
            raise SourceDocumentNotFoundError(
                f"No source markdown for publication {doc_id!r} at {path}"
            )
        text = path.read_text(encoding="utf-8")
        return SourceDocument(doc_id=doc_id, text=text, sha256=_digest(text), path=path)

    def available_ids(self) -> set[str]:
        if not self._dir.exists():
            return set()
        return {p.stem for p in self._dir.glob(f"*{FileExtensions.MARKDOWN}")}


class AbstractSourceLoader(DocumentSourceLoader):
    """Many abstracts per conference-year file, split on the abstract-ID header.

    Conference-year files are parsed once on first use and cached, since a single
    validation run reads every abstract in a year file.
    """

    def __init__(self, conference_dirs: dict[str, Path]) -> None:
        self._conference_dirs = conference_dirs
        self._documents: dict[str, SourceDocument] | None = None

    def load(self, doc_id: str) -> SourceDocument:
        document = self._index().get(doc_id)
        if document is None:
            raise SourceDocumentNotFoundError(
                f"No source abstract for {doc_id!r} in "
                f"{', '.join(str(d) for d in self._conference_dirs.values())}"
            )
        return document

    def available_ids(self) -> set[str]:
        return set(self._index())

    def _index(self) -> dict[str, SourceDocument]:
        if self._documents is None:
            self._documents = self._build_index()
        return self._documents

    def _build_index(self) -> dict[str, SourceDocument]:
        documents: dict[str, SourceDocument] = {}
        for conference, directory in self._conference_dirs.items():
            if not directory.exists():
                logger.warning("Abstract directory not found, skipping: %s", directory)
                continue
            for path in sorted(directory.glob(f"*{FileExtensions.MARKDOWN}")):
                match = _YEAR_FILE_RE.match(path.stem)
                if match is None:
                    logger.warning(
                        "Skipping abstract file with unexpected name: %s", path.name
                    )
                    continue
                documents.update(
                    self._split_year_file(
                        conference=conference, year=match.group("year"), path=path
                    )
                )
        return documents

    @staticmethod
    def _split_year_file(
        *, conference: str, year: str, path: Path
    ) -> dict[str, SourceDocument]:
        """Split one conference-year file the way the extraction pipeline does."""
        content = path.read_text(encoding="utf-8")
        documents: dict[str, SourceDocument] = {}
        for index, block in enumerate(content.split(_ABSTRACT_SPLIT_TOKEN)[1:]):
            first_line = block.strip().split("\n")[0].strip()
            raw_id = first_line if first_line else f"{index + 1:03d}"
            doc_id = f"{conference}_{year}_{raw_id}"
            text = _ABSTRACT_SPLIT_TOKEN + block
            documents[doc_id] = SourceDocument(
                doc_id=doc_id, text=text, sha256=_digest(text), path=path
            )
        return documents
