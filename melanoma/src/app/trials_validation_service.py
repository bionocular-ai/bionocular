"""LLM-as-a-Judge validation pipeline for extracted trial parameters.

Reads the extractor's ``results.json``, re-loads the exact source text the
extractor saw (snapshot-pinned), runs a deterministic pre-pass followed by a
Gemini judge pass, and routes each trial (keep / fix / drop / HITL). Mirrors the
extraction service's shape (config -> ``from_config`` factory -> collaborator
classes -> ``run()`` loop -> checkpoint -> merge-upsert writer) but adds bounded
concurrency, so the per-trial disk writes are guarded by a lock.

Authority is staged:
* ``apply_fixes=False`` (default, "2b") - the judge is advisory: PASS keeps,
  anything else routes to the HITL queue. Nothing is dropped/edited on its say-so.
* ``apply_fixes=True`` ("2c", enabled only after gold-set calibration) - FAIL with
  a gated correction is auto-fixed, FAIL without one is dropped.

The pure decision logic lives in module functions (``quote_grounded``,
``route_trial``) so it can be unit-tested without an LLM.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ..domain.structured_llm_interfaces import StructuredLLMService
from ..domain.trial_validation_models import (
    FieldEvaluation,
    TrialValidationResult,
    TrialValidationVerdict,
    ValidationDecision,
    ValidationFieldStatus,
    ValidationRunSummary,
)
from ..domain.trials_extraction_prompts import (
    BIOMARKER_VALUES,
    LINE_OF_THERAPY_VALUES,
    MODALITY_VALUES,
    PREVIOUS_TREATMENT_VALUES,
    STAGE_VALUES,
)
from ..domain.trials_validation_prompts import build_validation_prompt
from ..infrastructure.clinical_trials.snapshot_source import SnapshotTrialSource
from ..infrastructure.cost_calculator import CostCalculator
from ..infrastructure.trial_deterministic_validator import (
    DeterministicViolation,
    check_trial,
    is_droppable,
)

logger = logging.getLogger(__name__)

# Fields whose values are constrained to a controlled vocabulary.
_ENUM_VOCAB: dict[str, set[str]] = {
    "modality": set(MODALITY_VALUES),
    "biomarker": set(BIOMARKER_VALUES),
    "stage": set(STAGE_VALUES),
    "line_of_therapy": set(LINE_OF_THERAPY_VALUES),
    "previous_treatment_criteria": set(PREVIOUS_TREATMENT_VALUES),
}
# Fields serialised into the candidate JSON shown to the judge.
_CANDIDATE_FIELDS = (
    "nct_number",
    "cancer_type",
    "treatment_name",
    "modality",
    "biomarker",
    "stage",
    "line_of_therapy",
    "previous_treatment_criteria",
)
_MULTI_VALUE_SEP = "; "
_OPERATION = "validation"
# Rendered representations of a legitimately-empty extracted field.
_EMPTY_VALUE_TOKENS = {"", "[]", "null", "none"}


# ---------------------------------------------------------------------------
# Pure logic (no I/O) - unit-testable without an LLM
# ---------------------------------------------------------------------------


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _has_value(rendered: str) -> bool:
    """Whether a rendered extracted value is a real (non-empty) value."""
    return rendered.strip().lower() not in _EMPTY_VALUE_TOKENS


def quote_grounded(quote: str | None, source_text: str) -> bool:
    """True if `quote` is a (whitespace-normalised) literal substring of source.

    The hard anti-hallucination guard: a quote the judge did not actually copy
    from the source cannot ground a PASS or a fix.
    """
    if not quote or not quote.strip():
        return False
    return _collapse_ws(quote) in _collapse_ws(source_text)


def parse_corrected_value(field_name: str, corrected_text: str) -> list[str] | str:
    """Parse a judge `corrected_value` string into the record's native shape.

    Enum/list fields become a list filtered to in-vocabulary values; free-text
    fields (treatment_name) stay a string.
    """
    if field_name in _ENUM_VOCAB:
        vocab = _ENUM_VOCAB[field_name]
        return [
            v.strip()
            for v in corrected_text.split(_MULTI_VALUE_SEP)
            if v.strip() in vocab
        ]
    return corrected_text.strip()


def _fix_is_gated(
    ev: FieldEvaluation, source_text: str, score: float, threshold: float
) -> bool:
    """Whether a FAIL's proposed correction clears every safety gate."""
    if ev.corrected_value is None or not ev.corrected_value.strip():
        return False
    if score < threshold:
        return False
    if not quote_grounded(ev.source_evidence_quote, source_text):
        return False
    parsed = parse_corrected_value(ev.field_name, ev.corrected_value)
    # For enum fields the parse drops out-of-vocab values; an empty result means
    # the correction was not a valid vocabulary value.
    if ev.field_name in _ENUM_VOCAB and not parsed:
        return False
    if isinstance(parsed, str) and not parsed:
        return False
    return True


@dataclass
class RouteOutcome:
    decision: ValidationDecision
    applied_corrections: list[dict] = field(default_factory=list)


def route_trial(
    verdict: TrialValidationVerdict,
    source_text: str,
    apply_fixes: bool,
    score_threshold: float,
) -> RouteOutcome:
    """Decide a trial's fate from the judge verdict (pure).

    A PASS of a NON-EMPTY value must carry a grounded quote; an ungrounded "PASS"
    is treated as UNCERTAIN. A PASS of a legitimately-empty field needs no quote
    (there is nothing to cite). Detect-only (apply_fixes=False) never drops/fixes.
    """
    fails: list[FieldEvaluation] = []
    uncertain = False
    for ev in verdict.field_evaluations:
        status = ev.status
        if (
            status == ValidationFieldStatus.PASS
            and _has_value(ev.extracted_value)
            and not quote_grounded(ev.source_evidence_quote, source_text)
        ):
            status = ValidationFieldStatus.UNCERTAIN
        if status == ValidationFieldStatus.FAIL:
            fails.append(ev)
        elif status == ValidationFieldStatus.UNCERTAIN:
            uncertain = True

    if not fails and not uncertain:
        return RouteOutcome(ValidationDecision.KEPT)

    if not apply_fixes:
        # Advisory mode: never act on the judge, queue everything it flagged.
        return RouteOutcome(ValidationDecision.HITL)

    # Mature mode. UNCERTAIN always needs a human.
    if uncertain:
        return RouteOutcome(ValidationDecision.HITL)
    # Every FAIL must be gate-fixable, otherwise the row is dropped.
    corrections: list[dict] = []
    for ev in fails:
        if not _fix_is_gated(
            ev, source_text, verdict.validation_score, score_threshold
        ):
            return RouteOutcome(ValidationDecision.DROPPED)
        corrections.append(
            {
                "field": ev.field_name,
                "corrected": parse_corrected_value(
                    ev.field_name, ev.corrected_value or ""
                ),
                "evidence_quote": ev.source_evidence_quote,
                "score": verdict.validation_score,
            }
        )
    return RouteOutcome(ValidationDecision.FIXED, corrections)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class ValidationConfig:
    """Runtime configuration for a validation run."""

    results_path: Path
    snapshot_path: Path
    output_dir: Path
    model: str
    mode: str = "online"  # online | batch
    concurrency: int = 5
    apply_fixes: bool = False
    score_threshold: float = 0.75
    sample: int | None = None
    resume: bool = True
    dry_run: bool = False
    nct_allowlist: list[str] | None = None


# ---------------------------------------------------------------------------
# Checkpoint (resume across runs)
# ---------------------------------------------------------------------------


class ValidationCheckpointManager:
    """Persists which NCTs have been validated so a run can resume."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._done: dict[str, dict] = {}
        if path.exists():
            self._done = json.loads(path.read_text())

    def is_done(self, nct: str) -> bool:
        return nct in self._done

    def record(self, nct: str, decision: str) -> None:
        self._done[nct] = {
            "decision": decision,
            "recorded_at": datetime.utcnow().isoformat(),
        }
        self._path.write_text(json.dumps(self._done, indent=2))


# ---------------------------------------------------------------------------
# Result writer
# ---------------------------------------------------------------------------


class ValidationResultWriter:
    """Writes validation.json (merge-upsert) plus the derived routing files."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

    def write_validation(
        self,
        results: list[TrialValidationResult],
        summary: ValidationRunSummary,
    ) -> Path:
        path = self._output_dir / "validation.json"
        merged: dict[str, dict] = {}
        if path.exists():
            existing = json.loads(path.read_text())
            for row in existing.get("trials", []):
                merged[row["nct_number"]] = row
        for result in results:
            merged[result.nct_number] = result.to_dict()
        rows = list(merged.values())

        metadata = summary.to_dict()
        decisions = [r["decision"] for r in rows]
        metadata["total_trials"] = len(rows)
        metadata["kept"] = decisions.count(ValidationDecision.KEPT.value)
        metadata["fixed"] = decisions.count(ValidationDecision.FIXED.value)
        metadata["dropped"] = decisions.count(ValidationDecision.DROPPED.value)
        metadata["hitl"] = decisions.count(ValidationDecision.HITL.value)
        metadata["errored"] = decisions.count(ValidationDecision.ERROR.value)

        path.write_text(
            json.dumps(
                {"metadata": metadata, "trials": rows}, indent=2, ensure_ascii=False
            )
        )
        return path

    def write_derived(
        self,
        cleaned: list[dict],
        dropped: list[dict],
        hitl: list[dict],
        corrections: list[dict],
    ) -> None:
        """Write the cleaned cohort and the drop / HITL / corrections side files."""
        (self._output_dir / "results.cleaned.json").write_text(
            json.dumps({"trials": cleaned}, indent=2, ensure_ascii=False)
        )
        (self._output_dir / "results.cleaned.json.dropped-ncts.json").write_text(
            json.dumps({"dropped": dropped}, indent=2, ensure_ascii=False)
        )
        (self._output_dir / "validation_hitl.json").write_text(
            json.dumps({"trials": hitl}, indent=2, ensure_ascii=False)
        )
        (self._output_dir / "corrections.json").write_text(
            json.dumps({"corrections": corrections}, indent=2, ensure_ascii=False)
        )

    def write_cost_report(self, cost_calculator: CostCalculator) -> Path:
        """Write cost_report.json from the CostCalculator (parity with extraction).

        Written incrementally under the run's write-lock so a mid-run kill keeps
        the spend recorded up to that point.
        """
        path = self._output_dir / "cost_report.json"
        cost_calculator.save_detailed_report(str(path))
        return path


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class TrialValidationService:
    """Orchestrates deterministic + LLM validation over an extraction run."""

    def __init__(
        self,
        config: ValidationConfig,
        llm: StructuredLLMService,
        snapshot_source: SnapshotTrialSource,
        checkpoint: ValidationCheckpointManager,
        writer: ValidationResultWriter,
        cost_calculator: CostCalculator,
    ) -> None:
        self._config = config
        self._llm = llm
        self._snapshot = snapshot_source
        self._checkpoint = checkpoint
        self._writer = writer
        self._cost_calculator = cost_calculator
        self._write_lock = asyncio.Lock()

    @classmethod
    def from_config(
        cls,
        config: ValidationConfig,
        llm: StructuredLLMService,
        cost_calculator: CostCalculator,
    ) -> TrialValidationService:
        results = json.loads(config.results_path.read_text(encoding="utf-8"))
        _assert_snapshot_matches(results, config.snapshot_path)
        snapshot = json.loads(config.snapshot_path.read_text(encoding="utf-8"))
        return cls(
            config=config,
            llm=llm,
            snapshot_source=SnapshotTrialSource(snapshot),
            checkpoint=ValidationCheckpointManager(
                config.output_dir / "validation_checkpoint.json"
            ),
            writer=ValidationResultWriter(config.output_dir),
            cost_calculator=cost_calculator,
        )

    def _candidates(self) -> list[dict]:
        results = json.loads(self._config.results_path.read_text(encoding="utf-8"))
        trials = results.get("trials", [])
        if self._config.nct_allowlist:
            wanted = {n.upper() for n in self._config.nct_allowlist}
            trials = [t for t in trials if t["nct_number"].upper() in wanted]
        trials.sort(key=lambda t: t["nct_number"])
        if self._config.sample is not None:
            trials = trials[: self._config.sample]
        return trials

    async def _validate_one(self, record: dict) -> TrialValidationResult:
        nct = record["nct_number"]
        source_cancer_types = self._snapshot.get_cancer_types(nct)
        violations = check_trial(record, source_cancer_types)

        if is_droppable(violations):
            return TrialValidationResult(
                nct_number=nct,
                decision=ValidationDecision.DROPPED,
                is_valid=False,
                validation_score=0.0,
                deterministic_violations=[_violation_dict(v) for v in violations],
            )

        source_text = self._snapshot.load_trial(nct).full_text
        candidate_json = json.dumps(
            {k: record.get(k) for k in _CANDIDATE_FIELDS}, ensure_ascii=False, indent=2
        )
        prompt = build_validation_prompt(source_text, candidate_json)
        verdict = await self._llm.generate_structured(
            prompt,
            response_schema=TrialValidationVerdict,
            operation=_OPERATION,
            attribute_type="trial_validation",
        )
        outcome = route_trial(
            verdict,
            source_text,
            self._config.apply_fixes,
            self._config.score_threshold,
        )
        return TrialValidationResult(
            nct_number=nct,
            decision=outcome.decision,
            is_valid=verdict.is_valid,
            validation_score=verdict.validation_score,
            deterministic_violations=[_violation_dict(v) for v in violations],
            verdict=verdict.model_dump(mode="json"),
            applied_corrections=outcome.applied_corrections,
        )

    async def run(self) -> list[TrialValidationResult]:
        if self._config.mode == "batch":
            raise NotImplementedError(
                "Batch mode (Vertex Batch Prediction) is a documented follow-up; "
                "use --mode online for now."
            )

        run_start = datetime.utcnow()
        summary = ValidationRunSummary(
            model=self._config.model,
            run_date=run_start,
            mode=self._config.mode,
            apply_fixes=self._config.apply_fixes,
            source_snapshot_sha256=_sha256(self._config.snapshot_path),
        )

        candidates = self._candidates()
        pending = [
            c
            for c in candidates
            if not (self._config.resume and self._checkpoint.is_done(c["nct_number"]))
        ]
        logger.info(
            "Validation starting | candidates=%d pending=%d mode=%s apply_fixes=%s",
            len(candidates),
            len(pending),
            self._config.mode,
            self._config.apply_fixes,
        )

        if self._config.dry_run:
            logger.info("Dry run - %d trials would be validated.", len(pending))
            return []

        results: list[TrialValidationResult] = []
        semaphore = asyncio.Semaphore(max(1, self._config.concurrency))

        async def _worker(record: dict) -> None:
            async with semaphore:
                try:
                    result = await self._validate_one(record)
                except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
                    logger.error(
                        "Validation failed for %s: %s", record["nct_number"], exc
                    )
                    result = TrialValidationResult(
                        nct_number=record["nct_number"],
                        decision=ValidationDecision.ERROR,
                        error_message=str(exc),
                    )
                async with self._write_lock:
                    results.append(result)
                    self._checkpoint.record(result.nct_number, result.decision.value)
                    cost = self._cost_calculator.get_summary()
                    summary.total_cost_usd = cost.total_cost
                    summary.total_tokens = cost.total_tokens
                    self._writer.write_validation(results, summary)
                    self._writer.write_cost_report(self._cost_calculator)
                    logger.info(
                        "Validated %d/%d | %s | %s",
                        len(results),
                        len(pending),
                        result.nct_number,
                        result.decision.value,
                    )

        await asyncio.gather(*(_worker(record) for record in pending))

        self._write_derived_outputs(candidates)
        cost = self._cost_calculator.get_summary()
        summary.total_cost_usd = cost.total_cost
        summary.total_tokens = cost.total_tokens
        self._writer.write_validation(results, summary)
        self._writer.write_cost_report(self._cost_calculator)
        logger.info("Validation complete | %d trials", len(results))
        return results

    def _write_derived_outputs(self, candidates: list[dict]) -> None:
        """Recompute the cleaned cohort + side files from validation.json."""
        validation = json.loads(
            (self._config.output_dir / "validation.json").read_text()
        )
        verdicts = {r["nct_number"]: r for r in validation.get("trials", [])}
        by_nct = {c["nct_number"]: c for c in candidates}

        cleaned: list[dict] = []
        dropped: list[dict] = []
        hitl: list[dict] = []
        corrections: list[dict] = []

        for nct, vr in verdicts.items():
            record = by_nct.get(nct)
            if record is None:
                continue
            decision = vr["decision"]
            if decision == ValidationDecision.KEPT.value:
                cleaned.append(record)
            elif decision == ValidationDecision.FIXED.value:
                fixed = dict(record)
                for corr in vr.get("applied_corrections", []):
                    fixed[corr["field"]] = corr["corrected"]
                    corrections.append({"nct_number": nct, **corr})
                cleaned.append(fixed)
            elif decision == ValidationDecision.DROPPED.value:
                dropped.append(
                    {
                        "nct_number": nct,
                        "validation_score": vr.get("validation_score"),
                        "deterministic_violations": vr.get("deterministic_violations"),
                        "verdict": vr.get("verdict"),
                    }
                )
            else:  # HITL or ERROR both need a human
                hitl.append(vr)

        self._writer.write_derived(cleaned, dropped, hitl, corrections)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _violation_dict(v: DeterministicViolation) -> dict:
    return {
        "field": v.field,
        "rule": v.rule,
        "severity": v.severity,
        "detail": v.detail,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_snapshot_matches(results: dict, snapshot_path: Path) -> None:
    """Guard: the validator must grade against the snapshot the extractor used."""
    recorded = results.get("metadata", {}).get("snapshot_sha256")
    if recorded is None:
        logger.warning(
            "results.json has no snapshot_sha256; cannot verify source pinning. "
            "Re-run extraction so provenance is recorded."
        )
        return
    actual = _sha256(snapshot_path)
    if recorded != actual:
        raise ValueError(
            "Snapshot mismatch: results.json was produced from a different snapshot "
            f"(recorded {recorded[:12]}..., got {actual[:12]}...). The judge would "
            "grade against the wrong source. Pass the snapshot used for extraction."
        )
