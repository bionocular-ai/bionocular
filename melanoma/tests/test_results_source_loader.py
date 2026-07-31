"""Tests for the abstract / publication source loaders.

The abstract loader must reproduce the extractor's document split exactly - if it
slices differently, the judge grades a different text than the one the values came
from. The final assertions therefore run against the real corpus rather than a
hand-written fixture.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.infrastructure.document_source_loader import (
    AbstractSourceLoader,
    PublicationSourceLoader,
    SourceDocumentNotFoundError,
)

_MELANOMA_ROOT = Path(__file__).resolve().parent.parent
_ASCO_DIR = _MELANOMA_ROOT / "data" / "postprocessed" / "ASCO_Abstracts"
_ESMO_DIR = _MELANOMA_ROOT / "data" / "postprocessed" / "ESMO_Abstracts"
_PUBLICATIONS_DIR = _MELANOMA_ROOT / "data" / "postprocessed" / "Publications"

_ABSTRACT_MARKDOWN = """\
### Abstract ID: 9501

#### Title:
First trial.

#### Results:
ORR was 61.2%.

---

### Abstract ID: 9502

#### Title:
Second trial.

#### Results:
Median PFS was 10.2 months.
"""


@pytest.fixture()
def asco_dir(tmp_path: Path) -> Path:
    conference_dir = tmp_path / "ASCO_Abstracts"
    conference_dir.mkdir()
    (conference_dir / "ASCO_2023.md").write_text(_ABSTRACT_MARKDOWN, encoding="utf-8")
    return conference_dir


# ---------------------------------------------------------------------------
# PublicationSourceLoader
# ---------------------------------------------------------------------------


def test_publication_loader_reads_the_matching_markdown_file(tmp_path: Path) -> None:
    (tmp_path / "Batch-I_22.md").write_text("# Study\n\nORR 45%.", encoding="utf-8")
    loader = PublicationSourceLoader(tmp_path)

    doc = loader.load("Batch-I_22")

    assert doc.doc_id == "Batch-I_22"
    assert doc.text == "# Study\n\nORR 45%."
    assert doc.path == tmp_path / "Batch-I_22.md"


def test_publication_loader_hashes_the_exact_text_it_returns(tmp_path: Path) -> None:
    (tmp_path / "Batch-I_22.md").write_text("# Study", encoding="utf-8")

    doc = PublicationSourceLoader(tmp_path).load("Batch-I_22")

    assert doc.sha256 == hashlib.sha256(b"# Study").hexdigest()


def test_publication_loader_raises_for_an_unknown_doc_id(tmp_path: Path) -> None:
    loader = PublicationSourceLoader(tmp_path)

    with pytest.raises(SourceDocumentNotFoundError, match="Nope"):
        loader.load("Nope")


def test_publication_loader_lists_available_ids(tmp_path: Path) -> None:
    (tmp_path / "Batch-I_1.md").write_text("a", encoding="utf-8")
    (tmp_path / "Batch-II_2.md").write_text("b", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")

    assert PublicationSourceLoader(tmp_path).available_ids() == {
        "Batch-I_1",
        "Batch-II_2",
    }


# ---------------------------------------------------------------------------
# AbstractSourceLoader
# ---------------------------------------------------------------------------


def test_abstract_loader_keys_documents_by_conference_year_and_id(
    asco_dir: Path,
) -> None:
    loader = AbstractSourceLoader({"ASCO": asco_dir})

    assert loader.available_ids() == {"ASCO_2023_9501", "ASCO_2023_9502"}


def test_abstract_loader_restores_the_header_stripped_by_the_split(
    asco_dir: Path,
) -> None:
    """The extractor prepends '### Abstract ID:' back onto each block; so must we."""
    doc = AbstractSourceLoader({"ASCO": asco_dir}).load("ASCO_2023_9501")

    assert doc.text.startswith("### Abstract ID: 9501")
    assert "ORR was 61.2%." in doc.text


def test_abstract_loader_slices_only_the_requested_abstract(asco_dir: Path) -> None:
    doc = AbstractSourceLoader({"ASCO": asco_dir}).load("ASCO_2023_9501")

    assert "Second trial." not in doc.text
    assert "9502" not in doc.text


def test_abstract_loader_hashes_the_slice_not_the_whole_year_file(
    asco_dir: Path,
) -> None:
    loader = AbstractSourceLoader({"ASCO": asco_dir})
    first = loader.load("ASCO_2023_9501")
    second = loader.load("ASCO_2023_9502")
    whole_file = hashlib.sha256((asco_dir / "ASCO_2023.md").read_bytes()).hexdigest()

    assert first.sha256 != second.sha256
    assert first.sha256 != whole_file
    assert first.sha256 == hashlib.sha256(first.text.encode("utf-8")).hexdigest()


def test_abstract_loader_falls_back_to_a_positional_id_for_an_empty_block(
    tmp_path: Path,
) -> None:
    """Mirrors the extractor's `f"{idx+1:03d}"` fallback for an empty block."""
    conference_dir = tmp_path / "ESMO_Abstracts"
    conference_dir.mkdir()
    (conference_dir / "ESMO_2021.md").write_text(
        "### Abstract ID:\n\n### Abstract ID: 42\n\n#### Title:\nNumbered.\n",
        encoding="utf-8",
    )

    loader = AbstractSourceLoader({"ESMO": conference_dir})

    assert loader.available_ids() == {"ESMO_2021_001", "ESMO_2021_42"}


def test_abstract_loader_takes_the_id_from_the_first_non_blank_line(
    tmp_path: Path,
) -> None:
    """The extractor strips the block before reading line 1, so blank lines after
    the header are skipped - and a bare header inherits the next line as its id.
    Reproduced deliberately: parity with extraction beats a tidier rule."""
    conference_dir = tmp_path / "ESMO_Abstracts"
    conference_dir.mkdir()
    (conference_dir / "ESMO_2021.md").write_text(
        "### Abstract ID:\n\n#### Title:\nUnnumbered.\n", encoding="utf-8"
    )

    loader = AbstractSourceLoader({"ESMO": conference_dir})

    assert loader.available_ids() == {"ESMO_2021_#### Title:"}


def test_abstract_loader_raises_for_an_unknown_doc_id(asco_dir: Path) -> None:
    loader = AbstractSourceLoader({"ASCO": asco_dir})

    with pytest.raises(SourceDocumentNotFoundError, match="ASCO_2023_9999"):
        loader.load("ASCO_2023_9999")


def test_abstract_loader_ignores_directories_that_do_not_exist(tmp_path: Path) -> None:
    loader = AbstractSourceLoader({"ASCO": tmp_path / "missing"})

    assert loader.available_ids() == set()


# ---------------------------------------------------------------------------
# Against the real corpus
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _ASCO_DIR.exists(), reason="abstract corpus not present")
def test_abstract_loader_split_matches_the_extraction_pipeline_on_real_data() -> None:
    """Re-implements run_abstract_pipeline's split and asserts loader parity."""
    raw = (_ASCO_DIR / "ASCO_2023.md").read_text(encoding="utf-8")
    expected = {
        f"ASCO_2023_{block.strip().split(chr(10))[0].strip() or f'{idx + 1:03d}'}"
        for idx, block in enumerate(raw.split("### Abstract ID:")[1:])
    }

    loader = AbstractSourceLoader({"ASCO": _ASCO_DIR, "ESMO": _ESMO_DIR})
    asco_2023 = {i for i in loader.available_ids() if i.startswith("ASCO_2023_")}

    assert asco_2023 == expected
    assert len(asco_2023) == 110


@pytest.mark.skipif(
    not _PUBLICATIONS_DIR.exists(), reason="publication corpus not present"
)
def test_publication_loader_resolves_a_known_gold_set_document() -> None:
    doc = PublicationSourceLoader(_PUBLICATIONS_DIR).load("Batch-I_22")

    assert len(doc.text) > 1000
    assert doc.sha256 == hashlib.sha256(doc.text.encode("utf-8")).hexdigest()
