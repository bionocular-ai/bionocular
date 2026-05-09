"""Hold-out evaluation harness for the extraction-v2 pipeline.

Runs the new (or legacy) extraction pipeline against a curated set of
publication / abstract fixtures and scores precision / recall / cost / latency
against expected arm-attribute labels.

Usage::

    poetry run python3 scripts/eval_holdout.py --pipeline=new   [--out /tmp/new.json]
    poetry run python3 scripts/eval_holdout.py --pipeline=legacy [--out /tmp/legacy.json]
    poetry run python3 scripts/eval_holdout.py --dry-run

The ``--dry-run`` mode validates that fixtures + expected JSONs are present
and well-formed without making any Gemini calls.

Fixtures live in ``tests/fixtures/holdout/``; see ``MANIFEST.json`` for the
list. Expected labels were seeded from the deployed pipeline output and must
be manually curated by a human before the eval is meaningful.

Cost constants
--------------
Pricing for ``gemini-3.1-pro-preview`` is hardcoded below as a fallback. The
authoritative source is the ``CostCalculator`` wired into ``GeminiLLMService``
— this script reads the live cost from there. Update the constants if Google
publishes new rates and the calculator hasn't yet caught up.

Reference: https://ai.google.dev/gemini-api/docs/pricing
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

# Fallback pricing (USD per 1M tokens) for gemini-3.1-pro-preview.
# Used only if the live CostCalculator does not report a cost (e.g. legacy
# path with cost tracking disabled). See:
#   https://ai.google.dev/gemini-api/docs/pricing
GEMINI_31_PRO_INPUT_USD_PER_M: float = 1.25
GEMINI_31_PRO_OUTPUT_USD_PER_M: float = 5.00

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
FIXTURES_DIR: Path = REPO_ROOT / "tests" / "fixtures" / "holdout"
MANIFEST_PATH: Path = FIXTURES_DIR / "MANIFEST.json"


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), stderr=subprocess.DEVNULL
        )
        return out.decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _load_manifest() -> list[dict[str, Any]]:
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    fixtures = data.get("fixtures") or []
    if not isinstance(fixtures, list):
        raise ValueError("MANIFEST.json: 'fixtures' must be a list")
    return fixtures


def _load_fixture(doc_id: str) -> tuple[str, dict[str, Any]]:
    md_path = FIXTURES_DIR / f"{doc_id}.md"
    expected_path = FIXTURES_DIR / f"{doc_id}.expected.json"
    if not md_path.exists():
        raise FileNotFoundError(f"Missing fixture markdown: {md_path}")
    if not expected_path.exists():
        raise FileNotFoundError(f"Missing expected labels: {expected_path}")
    text = md_path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"Empty fixture markdown: {md_path}")
    with open(expected_path, encoding="utf-8") as f:
        expected = json.load(f)
    return text, expected


def _dry_run() -> int:
    fixtures = _load_manifest()
    print(f"Loaded MANIFEST.json — {len(fixtures)} fixtures")
    failures: list[str] = []
    for entry in fixtures:
        doc_id = entry.get("doc_id")
        if not isinstance(doc_id, str) or not doc_id:
            failures.append(f"manifest entry missing doc_id: {entry}")
            print(f"  [FAIL] manifest entry missing doc_id: {entry}")
            continue
        expected_arm_count = entry.get("expected_arm_count")
        try:
            text, expected = _load_fixture(doc_id)
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            failures.append(f"{doc_id}: {exc}")
            print(f"  [FAIL] {doc_id}: {exc}")
            continue
        arms = expected.get("arms") or {}
        n_arms = len(arms)
        match = "OK" if n_arms == expected_arm_count else "MISMATCH"
        print(
            f"  [{match}] {doc_id} ({entry.get('doc_type')}) — "
            f"{len(text)} chars, {n_arms} arms (expected {expected_arm_count})"
        )
        if n_arms != expected_arm_count:
            failures.append(
                f"{doc_id}: arm count {n_arms} != expected {expected_arm_count}"
            )
    if failures:
        print(f"\nDRY RUN FAILED: {len(failures)} issue(s)")
        return 1
    print(
        f"\nDRY RUN OK: {len(fixtures)} fixtures found, all parseable, ready to eval."
    )
    return 0


# --- Scoring helpers ------------------------------------------------------ #


def _norm_value(attr_name: str, raw: Any) -> str:
    """Normalize an attribute value for comparison.

    For numeric/structured attributes we try the deterministic validator;
    otherwise we lowercase + strip. Returns "" for missing values.
    """
    from src.domain.extraction_models import AttributeType
    from src.infrastructure.value_validator import validate_for_attribute

    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    if s.lower() in {"not found", "n/a", "na", "none"}:
        return ""
    try:
        attr = AttributeType(attr_name)
    except ValueError:
        return s.lower()
    ok, normalized, _reason = validate_for_attribute(attr, s)
    if ok and normalized:
        return str(normalized).strip().lower()
    return s.lower()


def _value_of(attr_data: Any) -> Any:
    """Pull the scalar value out of either {'value': ...} dict or raw scalar."""
    if isinstance(attr_data, dict):
        return attr_data.get("value")
    return attr_data


def _all_attribute_keys(arm_payload: dict[str, Any]) -> dict[str, Any]:
    """Return a flat {attr_name: value} map for an arm payload.

    Handles both the deployed JSON layout (top-level fields like
    ``generic_name`` plus a nested ``attributes`` dict) and the new path's
    output (same shape).
    """
    out: dict[str, Any] = {}
    attrs = arm_payload.get("attributes") or {}
    if isinstance(attrs, dict):
        for k, v in attrs.items():
            out[k] = _value_of(v)
    return out


def _map_arms_by_canonical(
    arm_results: dict[str, dict[str, Any]],
) -> dict[str, str]:
    """Return {canonical_generic_name: arm_id} for matching across runs."""
    from src.domain.drug_knowledge import canonicalize

    mapping: dict[str, str] = {}
    for arm_id, arm in arm_results.items():
        generic = arm.get("generic_name") or ""
        canon = canonicalize(generic).lower().strip()
        if canon and canon not in mapping:
            mapping[canon] = arm_id
    return mapping


def _score_doc(
    extracted: dict[str, dict[str, Any]],
    expected: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Score a single document.

    Returns a dict with arm-mapping accuracy plus per-(family,attribute)
    counts that the caller aggregates.
    """
    from src.domain.extraction_models import (
        FAMILY_TO_ATTRIBUTES,
    )

    attr_to_family: dict[str, str] = {}
    for family, attrs in FAMILY_TO_ATTRIBUTES.items():
        family_name = family.value if hasattr(family, "value") else str(family)
        for a in attrs:
            attr_to_family[a.value] = family_name

    extracted_map = _map_arms_by_canonical(extracted)
    expected_map = _map_arms_by_canonical(expected)

    matched_pairs: list[tuple[str, str]] = []  # (extracted_arm_id, expected_arm_id)
    for canon, exp_arm_id in expected_map.items():
        if canon in extracted_map:
            matched_pairs.append((extracted_map[canon], exp_arm_id))

    arms_expected = len(expected)
    arms_matched = len(matched_pairs)

    # Per-family aggregation
    per_family: dict[str, dict[str, int]] = {}

    def _bump(family: str, key: str, n: int = 1) -> None:
        per_family.setdefault(
            family, {"n_expected": 0, "n_extracted": 0, "n_correct": 0}
        )[key] += n

    for ext_arm_id, exp_arm_id in matched_pairs:
        ext_attrs = _all_attribute_keys(extracted[ext_arm_id])
        exp_attrs = _all_attribute_keys(expected[exp_arm_id])
        all_keys = set(ext_attrs.keys()) | set(exp_attrs.keys())
        for key in all_keys:
            family = attr_to_family.get(key)
            if family is None:
                # Unknown attr (not in any family) — skip silently
                continue
            ext_v = _norm_value(key, ext_attrs.get(key))
            exp_v = _norm_value(key, exp_attrs.get(key))
            if exp_v:
                _bump(family, "n_expected")
            if ext_v:
                _bump(family, "n_extracted")
            if exp_v and ext_v and ext_v == exp_v:
                _bump(family, "n_correct")

    # Unmatched expected arms still contribute to recall denominator
    matched_exp_ids = {exp for _, exp in matched_pairs}
    for exp_arm_id, exp_payload in expected.items():
        if exp_arm_id in matched_exp_ids:
            continue
        for key, raw in _all_attribute_keys(exp_payload).items():
            family = attr_to_family.get(key)
            if family is None:
                continue
            if _norm_value(key, raw):
                _bump(family, "n_expected")

    return {
        "arms_expected": arms_expected,
        "arms_matched": arms_matched,
        "per_family": per_family,
    }


# --- Pipeline wiring (mirrors run_publication_pipeline.py) ---------------- #


async def _build_services() -> tuple[Any, Any, Any]:
    """Wire EnhancedExtractionService for eval.

    Returns (extraction_service, cost_calculator, vector_store_service).
    """
    from src.app.enhanced_extraction_service import EnhancedExtractionService
    from src.domain.models import ChunkingConfiguration
    from src.infrastructure.arm_aware_rag_provider import ArmAwareRAGContextProvider
    from src.infrastructure.attribute_extractor import LLMAttributeExtractor
    from src.infrastructure.cost_calculator import CostCalculator, ModelType
    from src.infrastructure.family_extractor import FamilyExtractor
    from src.infrastructure.gemini_service import GeminiLLMService
    from src.infrastructure.langchain.chunking import LangChainChunkingService
    from src.infrastructure.langchain.embeddings import LangChainEmbeddingService
    from src.infrastructure.langchain.vector_store import LangChainVectorStore
    from src.infrastructure.prompt_templates import ExtractionPromptTemplateProvider
    from src.infrastructure.treatment_arm_separator import TreatmentArmSeparator

    google_api_key = os.getenv("GOOGLE_API_KEY", "")
    if not google_api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set in the environment")

    cost_calculator = CostCalculator(
        default_model=ModelType.GEMINI_31_PRO_PREVIEW_DIRECT
    )
    llm_service = GeminiLLMService(
        api_key=google_api_key,
        model=ModelType.GEMINI_31_PRO_PREVIEW_DIRECT.value,
        cost_calculator=cost_calculator,
    )

    embedding_service = LangChainEmbeddingService()
    vector_store_service = LangChainVectorStore(
        embedding_service=embedding_service,
        collection_name="holdout_eval_trials",
        persist_directory=None,
    )
    chunking_config = ChunkingConfiguration(
        max_chunk_size=1000,
        chunk_overlap=200,
        preserve_tables=True,
        include_headers=True,
    )
    chunking_strategy = LangChainChunkingService(chunking_config)
    rag_provider = ArmAwareRAGContextProvider(
        vector_store=vector_store_service,
        embedding_service=embedding_service,
    )

    arm_separator = TreatmentArmSeparator(llm_service=llm_service)
    prompt_provider = ExtractionPromptTemplateProvider()
    attribute_extractor = LLMAttributeExtractor(
        llm_service=llm_service,
        prompt_provider=prompt_provider,
    )
    family_extractor = FamilyExtractor(gemini=llm_service)

    extraction_service = EnhancedExtractionService(
        treatment_arm_separator=arm_separator,
        arm_aware_rag_provider=rag_provider,
        attribute_extractor=attribute_extractor,
        llm_service=llm_service,
        clinical_trials_api_service=None,
        enable_cost_tracking=False,
        max_concurrent_attributes=20,
        family_extractor=family_extractor,
        gemini=llm_service,
    )

    # Stash chunking deps on the service so the runner can pre-embed legacy
    # paths if needed. The new path doesn't need RAG embedding.
    extraction_service._eval_chunking_strategy = chunking_strategy  # type: ignore[attr-defined]
    extraction_service._eval_embedding_service = embedding_service  # type: ignore[attr-defined]
    extraction_service._eval_chunking_config = chunking_config  # type: ignore[attr-defined]

    return extraction_service, cost_calculator, vector_store_service


async def _embed_for_legacy(
    extraction_service: Any,
    vector_store_service: Any,
    text: str,
    doc_id: str,
) -> None:
    """Embed a doc into the vector store (needed for the legacy RAG path)."""
    from src.domain.models import ChunkWithEmbedding, EmbeddingConfiguration

    chunking_strategy = extraction_service._eval_chunking_strategy
    embedding_service = extraction_service._eval_embedding_service
    chunking_config = extraction_service._eval_chunking_config

    chunks = await chunking_strategy.chunk_content(
        content=text,
        configuration=chunking_config,
        document_id=doc_id,
        filename=doc_id,
    )
    if not chunks:
        return
    embedding_config = EmbeddingConfiguration()
    embeddings = await embedding_service.generate_embeddings_batch(
        [c.content for c in chunks], embedding_config
    )
    chunks_with_embeddings = [
        ChunkWithEmbedding(
            id=c.id,
            document_id=c.document_id,
            content=c.content,
            chunk_type=c.chunk_type,
            metadata=c.metadata,
            sequence_number=c.sequence_number,
            token_count=c.token_count,
            created_at=c.created_at,
            embedding=emb,
        )
        for c, emb in zip(chunks, embeddings)
    ]
    await vector_store_service.upsert_chunks(chunks_with_embeddings)


def _serialize_arm_results(arm_results: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Convert TreatmentArmExtractionResult.arm_results into JSON-friendly dict."""
    out: dict[str, dict[str, Any]] = {}
    for arm_id, arm in arm_results.items():
        attrs_in = arm.get("attributes") or {}
        attrs_out: dict[str, Any] = {}
        for k, v in attrs_in.items():
            if isinstance(v, dict):
                attrs_out[str(k)] = {"value": v.get("value")}
            elif hasattr(v, "value"):
                attrs_out[str(k)] = {"value": getattr(v, "value", None)}
            else:
                attrs_out[str(k)] = {"value": v}
        out[arm_id] = {
            "arm_id": arm.get("arm_id"),
            "arm_name": arm.get("arm_name"),
            "generic_name": arm.get("generic_name"),
            "dose": arm.get("dose"),
            "dosing_schedule": arm.get("dosing_schedule"),
            "patient_count": arm.get("patient_count"),
            "arm_type": arm.get("arm_type"),
            "combination_drugs": arm.get("combination_drugs", []),
            "attributes": attrs_out,
        }
    return out


def _load_legacy_arm_results(doc_id: str, doc_type: str) -> dict[str, Any]:
    """Load pre-extracted arm_results from the deployed legacy files."""
    data_dir = REPO_ROOT / "data" / "deployed"
    if doc_type == "abstract":
        path = data_dir / "extraction_results_ASCO_2024.json"
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        for entry in raw.get("abstracts", []):
            if entry["abstract_id"] == doc_id:
                return entry.get("arm_results") or {}
    else:
        path = data_dir / "extraction_results_Publications_20260412_102203.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        for entry in raw.get("publications", []):
            if entry["pub_id"] == doc_id:
                return entry.get("arm_results") or {}
    return {}


def _emit_output(
    pipeline: str,
    per_family_totals: dict[str, dict[str, int]],
    per_doc: list[dict[str, Any]],
    arms_expected_total: int,
    arms_matched_total: int,
    total_latency_ms: int = 0,
    total_tokens_in: int = 0,
    total_tokens_out: int = 0,
    total_cost: float = 0.0,
    out_path: Path | None = None,
) -> None:
    fixtures = _load_manifest()
    per_family_out: dict[str, dict[str, float | int]] = {}
    for fam, counts in per_family_totals.items():
        n_exp = counts["n_expected"]
        n_ext = counts["n_extracted"]
        n_cor = counts["n_correct"]
        per_family_out[fam] = {
            "precision": round(n_cor / n_ext, 4) if n_ext else 0.0,
            "recall": round(n_cor / n_exp, 4) if n_exp else 0.0,
            "n_expected": n_exp,
            "n_extracted": n_ext,
            "n_correct": n_cor,
        }
    arm_mapping_accuracy = (
        round(arms_matched_total / arms_expected_total, 4)
        if arms_expected_total
        else 0.0
    )
    output = {
        "pipeline": pipeline,
        "git_sha": _git_sha(),
        "prompt_version": "v2.0",
        "totals": {
            "docs": len(fixtures),
            "arms_expected": arms_expected_total,
            "arms_matched": arms_matched_total,
            "arm_mapping_accuracy": arm_mapping_accuracy,
        },
        "per_family": per_family_out,
        "per_doc": per_doc,
        "summary": {
            "total_latency_ms": total_latency_ms,
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "total_cost_usd": round(total_cost, 6),
        },
    }
    if out_path is not None:
        out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
        print(f"\nResults written to {out_path}")
    _print_summary(output)


async def _run_eval_legacy_cached(out_path: Path | None) -> int:
    fixtures = _load_manifest()
    per_doc: list[dict[str, Any]] = []
    per_family_totals: dict[str, dict[str, int]] = {}
    arms_expected_total = arms_matched_total = 0

    for entry in fixtures:
        doc_id = entry["doc_id"]
        doc_type = entry["doc_type"]
        _, expected = _load_fixture(doc_id)
        expected_arms = expected.get("arms") or {}

        extracted_arms = _load_legacy_arm_results(doc_id, doc_type)
        if not extracted_arms:
            print(f"[WARN] {doc_id}: no legacy arm_results found — skipping")
            continue

        scored = _score_doc(extracted_arms, expected_arms)
        arms_expected_total += scored["arms_expected"]
        arms_matched_total += scored["arms_matched"]
        for fam, counts in scored["per_family"].items():
            agg = per_family_totals.setdefault(
                fam, {"n_expected": 0, "n_extracted": 0, "n_correct": 0}
            )
            for k, v in counts.items():
                agg[k] += v
        per_doc.append(
            {
                "doc_id": doc_id,
                "doc_type": doc_type,
                "latency_ms": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "estimated_cost_usd": 0.0,
                "arms_expected": scored["arms_expected"],
                "arms_matched": scored["arms_matched"],
            }
        )

    _emit_output(
        "legacy-cached",
        per_family_totals,
        per_doc,
        arms_expected_total,
        arms_matched_total,
        out_path=out_path,
    )
    return 0


async def _run_eval(pipeline: str, out_path: Path | None) -> int:
    if pipeline == "legacy-cached":
        return await _run_eval_legacy_cached(out_path)

    from src.domain.models import DocumentType

    if pipeline == "legacy":
        os.environ["USE_LEGACY_RAG_EXTRACTION"] = "1"
    else:
        os.environ.pop("USE_LEGACY_RAG_EXTRACTION", None)

    fixtures = _load_manifest()
    extraction_service, cost_calculator, vector_store_service = await _build_services()

    per_doc: list[dict[str, Any]] = []
    per_family_totals: dict[str, dict[str, int]] = {}
    arms_expected_total = 0
    arms_matched_total = 0
    total_latency_ms = 0
    total_tokens_in = 0
    total_tokens_out = 0
    total_cost = 0.0

    for entry in fixtures:
        doc_id = entry["doc_id"]
        doc_type_str = entry["doc_type"]
        doc_type = (
            DocumentType.PUBLICATION
            if doc_type_str == "publication"
            else DocumentType.ABSTRACT
        )
        text, expected = _load_fixture(doc_id)
        expected_arms = expected.get("arms") or {}

        # Snapshot cost calculator before this fixture
        before_calls = len(cost_calculator.api_calls)

        if pipeline == "legacy":
            await _embed_for_legacy(
                extraction_service, vector_store_service, text, doc_id
            )

        t0 = time.perf_counter()
        try:
            result = await extraction_service.extract(text, doc_id, doc_type)
        except (RuntimeError, ValueError) as exc:
            print(f"[ERROR] {doc_id}: {exc}")
            per_doc.append(
                {
                    "doc_id": doc_id,
                    "error": str(exc),
                    "latency_ms": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "estimated_cost_usd": 0.0,
                }
            )
            continue
        latency_ms = int((time.perf_counter() - t0) * 1000)

        # Aggregate per-fixture cost from new calls only
        new_calls = cost_calculator.api_calls[before_calls:]
        tokens_in = sum(c.prompt_tokens for c in new_calls)
        tokens_out = sum(c.completion_tokens for c in new_calls)
        cost_usd = sum(c.cost for c in new_calls)
        if cost_usd == 0.0 and (tokens_in or tokens_out):
            cost_usd = (
                tokens_in / 1_000_000 * GEMINI_31_PRO_INPUT_USD_PER_M
                + tokens_out / 1_000_000 * GEMINI_31_PRO_OUTPUT_USD_PER_M
            )

        extracted_arms = _serialize_arm_results(result.arm_results)
        scored = _score_doc(extracted_arms, expected_arms)
        arms_expected_total += scored["arms_expected"]
        arms_matched_total += scored["arms_matched"]
        for fam, counts in scored["per_family"].items():
            agg = per_family_totals.setdefault(
                fam, {"n_expected": 0, "n_extracted": 0, "n_correct": 0}
            )
            for k, v in counts.items():
                agg[k] += v

        per_doc.append(
            {
                "doc_id": doc_id,
                "doc_type": doc_type_str,
                "latency_ms": latency_ms,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "estimated_cost_usd": round(cost_usd, 6),
                "arms_expected": scored["arms_expected"],
                "arms_matched": scored["arms_matched"],
                "extracted_arms": extracted_arms,
            }
        )
        total_latency_ms += latency_ms
        total_tokens_in += tokens_in
        total_tokens_out += tokens_out
        total_cost += cost_usd

        # Reset vector store between docs to avoid cross-contamination
        try:
            await vector_store_service.clear_store()
        except (RuntimeError, AttributeError):
            pass

    _emit_output(
        pipeline,
        per_family_totals,
        per_doc,
        arms_expected_total,
        arms_matched_total,
        total_latency_ms=total_latency_ms,
        total_tokens_in=total_tokens_in,
        total_tokens_out=total_tokens_out,
        total_cost=total_cost,
        out_path=out_path,
    )
    return 0


def _print_summary(output: dict[str, Any]) -> None:
    print("\n" + "=" * 70)
    print(f"HOLD-OUT EVAL — pipeline={output['pipeline']} sha={output['git_sha'][:8]}")
    print("=" * 70)
    t = output["totals"]
    s = output["summary"]
    print(
        f"docs={t['docs']}  arms_expected={t['arms_expected']}  "
        f"arms_matched={t['arms_matched']}  "
        f"arm_mapping_accuracy={t['arm_mapping_accuracy']:.2%}"
    )
    print(
        f"latency={s['total_latency_ms']}ms  "
        f"tokens_in={s['total_tokens_in']}  tokens_out={s['total_tokens_out']}  "
        f"cost=${s['total_cost_usd']:.4f}"
    )
    print("\nPer-family precision / recall:")
    print(f"  {'family':<22} {'P':>8} {'R':>8} {'n_exp':>8} {'n_ext':>8} {'n_cor':>8}")
    for fam, m in sorted(output["per_family"].items()):
        print(
            f"  {fam:<22} {m['precision']:>8.2%} {m['recall']:>8.2%} "
            f"{m['n_expected']:>8} {m['n_extracted']:>8} {m['n_correct']:>8}"
        )
    print("\nPer-doc:")
    print(
        f"  {'doc_id':<24} {'lat(ms)':>9} {'tok_in':>8} {'tok_out':>8} "
        f"{'$':>9} {'arms':>10}"
    )
    for d in output["per_doc"]:
        if "error" in d:
            print(f"  {d['doc_id']:<24} ERROR: {d['error']}")
            continue
        arms_str = f"{d.get('arms_matched', 0)}/{d.get('arms_expected', 0)}"
        print(
            f"  {d['doc_id']:<24} {d['latency_ms']:>9} {d['tokens_in']:>8} "
            f"{d['tokens_out']:>8} ${d['estimated_cost_usd']:>8.4f} {arms_str:>10}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pipeline",
        choices=["new", "legacy", "legacy-cached"],
        default="new",
        help="Which extraction path to run. 'legacy-cached' scores pre-extracted deployed data without LLM calls.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional path to write the full JSON report.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate fixtures + manifest only; no Gemini calls.",
    )
    args = parser.parse_args()

    if args.dry_run:
        return _dry_run()

    return asyncio.run(_run_eval(args.pipeline, args.out))


if __name__ == "__main__":
    raise SystemExit(main())
